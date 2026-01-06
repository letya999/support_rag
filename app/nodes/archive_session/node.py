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
    Generate a full transcript summary for the session.
    Combines conversation_history with the current Q&A.
    """
    history = state.get("conversation_history", []) or []
    lines = []
    
    # Add past history
    for msg in history:
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content", "")
        if role == "Assistant":  # Filter system messages from history if needed, though history usually has final answers
             if _is_system_message(content):
                 continue
        lines.append(f"{role}: {content}")
    
    # Add current turn
    # Note: conversation_history might NOT include the current turn yet depending on when this node runs.
    # Usually it contains PAST turns. We append the current Q and A.
    
    # Check if the last message in history is the current question to avoid duplication
    current_question = state.get("question", "")
    if not history or history[-1].get("content") != current_question:
        lines.append(f"User: {current_question}")
    
    # Add current answer
    clean_answer = _filter_answer(answer)
    if clean_answer:
        lines.append(f"Assistant: {clean_answer}")
    
    return "\n".join(lines)


class ArchiveSessionNode(BaseNode):
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
            
            # Feature Request: Save extracted facts to memory
            entities = state.get("extracted_entities", {})
            if entities:
                # We treat extracted entities as "memory facts" for now
                profile_update.update(entities)
            
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
                
                # We need a proper DB connection here as PersistenceManager helpers are atomic
                # To do "SELECT then UPDATE" safely or efficiently we might need to extend PersistenceManager
                # But for now, let's use the public helper method but currently it doesn't support merging logic inside SQL.
                # We must implement the merge logic inside the node using raw SQL or update PersistenceManager.
                # Let's use raw SQL here for the complex merge as previously attempted, 
                # BUT we need to obtain a connection first.
                
                from app.storage.connection import get_db_connection
                async with get_db_connection() as conn:
                    async with conn.cursor() as cur:
                         # Fetch existing metrics first to merge
                        await cur.execute("SELECT metrics FROM sessions_archive WHERE session_id = %s", (session_id,))
                        existing_row = await cur.fetchone()
                        existing_metrics = existing_row[0] if existing_row and existing_row[0] else {}

                        # Merge logic
                        merged_metrics = {
                            "confidence": metrics.get("confidence", 0), # Current confidence
                            "min_confidence": min(existing_metrics.get("min_confidence", 100), metrics.get("confidence", 100)),
                            "total_attempts": existing_metrics.get("total_attempts", 0) + 1,
                            "retrieved_docs_count": metrics.get("retrieved_docs_count", 0),
                            "dialog_state": metrics.get("dialog_state"),
                            "routing_action": metrics.get("routing_action"),
                            "interactions_count": existing_metrics.get("interactions_count", 0) + 1
                        }
                        
                        # Duration placeholder (state doesn't track duration yet, pass 0 or None)
                        duration_seconds = 0 
                        
                        await cur.execute(
                            """
                            INSERT INTO sessions_archive (session_id, user_id, outcome, summary, metrics, duration_seconds, end_time)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            ON CONFLICT (session_id) DO UPDATE SET
                                outcome = EXCLUDED.outcome,
                                summary = EXCLUDED.summary,
                                metrics = %s,
                                duration_seconds = EXCLUDED.duration_seconds,
                                end_time = NOW()
                            """,
                            (session_id, user_id, outcome, summary, json.dumps(merged_metrics), duration_seconds, json.dumps(merged_metrics))
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
