"""
Archive Session Node.

Finalizes and archives session data to PostgreSQL.
Filters system messages before saving to keep history clean.
"""
from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.nodes.persistence import PersistenceManager
from app.cache.session_manager import SessionManager
from app.cache.cache_layer import get_cache_manager
from app.observability.tracing import observe


def _get_params() -> Dict[str, Any]:
    """Get node parameters from centralized config."""
    try:
        from app.services.config_loader.loader import get_node_params
        return get_node_params("archive_session")
    except Exception:
        return {}


def _is_system_message(content: str) -> bool:
    """Check if content is a system message that should be filtered."""
    try:
        from app.nodes._shared_config.history_filter import is_system_message
        return is_system_message(content)
    except ImportError:
        return False


def _filter_answer(answer: str) -> str:
    """
    Filter system phrases from answer before archiving.
    Returns empty string if answer is purely a system message.
    """
    if _is_system_message(answer):
        return ""
    return answer


def _generate_summary(state: Dict[str, Any], answer: str) -> str:
    """
    Generate a clean summary for the session.
    Filters out system messages.
    """
    # Use aggregated query or original question
    question = state.get("aggregated_query") or state.get("question", "")
    
    # Filter the answer
    clean_answer = _filter_answer(answer)
    
    if clean_answer:
        return f"Q: {question}\nA: {clean_answer}"
    else:
        return f"Q: {question}"


class ArchiveSessionNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalize and archive session.
        Filters system messages before saving to keep history clean.
        """
        params = _get_params()
        filter_system = params.get("filter_system_messages", True)
        save_to_postgres = params.get("save_to_postgres", True)
        
        user_id = state.get("user_id")
        session_id = state.get("session_id")
        
        if not user_id or not session_id:
            return {}

        outcome = state.get("dialog_state", "active")
        answer = state.get("answer", "")
        
        # Filter system messages from answer if enabled
        if filter_system:
            answer = _filter_answer(answer)
        
        # 1. Update User Profile if we have new info
        try:
            profile_update = {
                "last_answer_confidence": state.get("confidence", 0),
                "last_interaction": True
            }
            await PersistenceManager.save_user_profile_update(user_id, profile_update)
        except Exception as e:
            print(f"⚠️ Error updating profile: {e}")

        # 2. Archive Session
        if save_to_postgres:
            try:
                metrics = {
                    "confidence": state.get("confidence", 0),
                    "retrieved_docs_count": len(state.get("docs", [])),
                    "attempt_count": state.get("attempt_count", 0),
                    "dialog_state": state.get("dialog_state", "INITIAL"),
                    "routing_action": state.get("action", "unknown")
                }
                
                # Generate clean summary (filtered)
                summary = _generate_summary(state, state.get("answer", ""))
                
                await PersistenceManager.archive_session(
                    session_id=session_id,
                    user_id=str(user_id),
                    outcome=outcome,
                    summary=summary,
                    metrics=metrics
                )
                
                # 3. Save Searchable Summary (only if answer is meaningful)
                if answer and not _is_system_message(answer):
                    await PersistenceManager.save_session_summary(
                        session_id=session_id,
                        summary_text=summary,
                        tags=list(state.get("extracted_entities", {}).keys())
                    )
            except Exception as e:
                print(f"⚠️ Error archiving session: {e}")

        # 3. Update Active Session State (Redis)
        try:
            cache_manager = await get_cache_manager()
            if cache_manager.redis_client:
                session_manager = SessionManager(cache_manager.redis_client)
                state_updates = {
                    "dialog_state": state.get("dialog_state", "INITIAL"),
                    "attempt_count": state.get("attempt_count", 0),
                    "last_answer_confidence": state.get("confidence", 0)
                }
                
                # Update extracted entities if present
                if state.get("extracted_entities"):
                    state_updates["extracted_entities"] = state.get("extracted_entities")
                    
                await session_manager.update_state(session_id, state_updates)
        except Exception as e:
            print(f"⚠️ Error updating Redis session: {e}")

        return {"session_archived": True}


# Singleton instance
archive_session_node = ArchiveSessionNode()
