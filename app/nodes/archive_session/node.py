"""
Archive Session Node.

Finalizes and archives session data to PostgreSQL.
Filters system messages before saving to keep history clean.
"""
from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.storage.persistence import PersistenceManager
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
        if isinstance(msg, dict):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "type", "unknown")
            content = getattr(msg, "content", "")
            
        role = role.capitalize()
        if role == "Assistant":  # Filter system messages from history if needed, though history usually has final answers
             if _is_system_message(content):
                 continue
        lines.append(f"{role}: {content}")
    
    # Add current turn
    # Note: conversation_history might NOT include the current turn yet depending on when this node runs.
    # Usually it contains PAST turns. We append the current Q and A.
    
    # Check if the last message in history is the current question to avoid duplication
    current_question = state.get("question", "")
    
    last_msg_content = ""
    if history:
        last_msg = history[-1]
        if isinstance(last_msg, dict):
            last_msg_content = last_msg.get("content", "")
        else:
            last_msg_content = getattr(last_msg, "content", "")
            
    if not history or last_msg_content != current_question:
        lines.append(f"User: {current_question}")
    
    # Add current answer
    clean_answer = _filter_answer(answer)
    if clean_answer:
        lines.append(f"Assistant: {clean_answer}")
    
    return "\n".join(lines)


class ArchiveSessionNode(BaseNode):
    """
    Archives session data to PostgreSQL and updates Redis.
    
    Contracts:
        Input:
            Required:
                - user_id (str): User identifier
                - session_id (str): Session identifier
                - question (str): Current question
                - answer (str): Generated answer
            Optional:
                - escalation_triggered (bool): Whether escalation happened
                - escalation_reason (str): Reason for escalation
                - confidence (float): Answer confidence
                - attempt_count (int): Number of attempts
                - detected_language (str): Detected language
                - sentiment (Dict): Sentiment analysis
                - translated_query (str): Translated query
                - matched_intent (str): Matched intent
                - docs (List[str]): Retrieved documents
                - safety_violation (bool): Safety flag
                - extracted_entities (Dict): Entities to persist
                - dialog_state (str): Current state
        
        Output:
            Guaranteed:
                - session_archived (bool): Whether archiving succeeded
            Conditional:
                - error (str): Error message if failed
    """
    
    INPUT_CONTRACT = {
        "required": ["user_id", "session_id", "question", "answer"],
        "optional": [
            "escalation_triggered",
            "escalation_reason",
            "confidence",
            "attempt_count",
            "detected_language",
            "sentiment",
            "translated_query",
            "matched_intent",
            "docs",
            "safety_violation",
            "extracted_entities",
            "dialog_state",
            "conversation_history"
        ]
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["session_archived"],
        "conditional": ["error"]
    }
    
    def __init__(self):
        super().__init__("archive_session")

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Save message and update session metadata."""
        user_id = state.get("user_id")
        session_id = state.get("session_id")
        question = state.get("question", "")
        answer = state.get("answer", "")
        
        if not user_id or not session_id:
            return {}
        
        try:
            # 1. Update session metadata (Ensure session exists first)
            status = "escalated" if state.get("escalation_triggered") else "active"
            await PersistenceManager.update_session(
                session_id=session_id,
                user_id=user_id,
                channel="telegram",  # TODO: get from state or config
                status=status,
                metadata={
                    "last_confidence": state.get("confidence", 0),
                    "attempt_count": state.get("attempt_count", 0)
                }
            )

            # 2. Save user message
            if question:
                await PersistenceManager.save_message(
                    session_id=session_id,
                    user_id=user_id,
                    role="user",
                    content=question,
                    metadata={
                        "detected_language": state.get("detected_language"),
                        "sentiment": state.get("sentiment"),
                        "translated": state.get("translated_query")  # Save English translation for loop detection
                    }
                )
            
            # 3. Save assistant response (filter system messages)
            if answer and not _is_system_message(answer):
                await PersistenceManager.save_message(
                    session_id=session_id,
                    user_id=user_id,
                    role="assistant",
                    content=answer,
                    metadata={
                        "confidence": state.get("confidence"),
                        "matched_intent": state.get("matched_intent"),
                        "docs_count": len(state.get("docs", []))
                    }
                )
            
            # 4. Save escalation if triggered
            if state.get("escalation_triggered"):
                priority = "high" if state.get("safety_violation") else "normal"
                await PersistenceManager.save_escalation(
                    session_id=session_id,
                    reason=state.get("escalation_reason", "unknown"),
                    priority=priority
                )
            
            # 5. Update user profile
            if state.get("extracted_entities"):
                await PersistenceManager.save_user_profile_update(
                    user_id=user_id,
                    memory_update=state.get("extracted_entities")
                )
            
        except Exception as e:
            print(f"⚠️ Error archiving session: {e}")
            return {"session_archived": False, "error": str(e)}
        
        # 6. Update Redis session state (optional cache layer)
        try:
            cache_manager = await get_cache_manager()
            if cache_manager.redis_client:
                session_manager = SessionManager(cache_manager.redis_client)
                await session_manager.update_state(session_id, {
                    "dialog_state": state.get("dialog_state"),
                    "attempt_count": state.get("attempt_count", 0),
                     # Add extracted entities to Redis for continuity
                    "extracted_entities": state.get("extracted_entities")
                })
        except Exception as e:
            print(f"⚠️ Redis update failed (non-critical): {e}")
        
        return {"session_archived": True}
        
# Singleton instance
archive_session_node = ArchiveSessionNode()
