from typing import Dict, Any
from app.nodes.base_node import BaseNode
from app.nodes.persistence import PersistenceManager
from app.observability.tracing import observe

class ArchiveSessionNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalize and archive session if needed.
        """
        user_id = state.get("user_id")
        session_id = state.get("session_id")
        
        if not user_id or not session_id:
            return {}

        outcome = state.get("dialog_state", "active")
        answer = state.get("answer", "")
        
        # 1. Update User Profile if we have new info
        # In a real app, we would extract facts. Here we just update last_seen and maybe some meta.
        try:
            profile_update = {
                "last_answer_confidence": state.get("confidence", 0),
                "last_interaction": True
            }
            await PersistenceManager.save_user_profile_update(user_id, profile_update)
        except Exception as e:
            print(f"⚠️ Error updating profile: {e}")

        # 2. Archive Session
        # We archive if it's a final state or just every turn (updating the same record)
        try:
            metrics = {
                "confidence": state.get("confidence", 0),
                "retrieved_docs_count": len(state.get("docs", [])),
                "attempt_count": state.get("attempt_count", 0)
            }
            
            # Use aggregated query or answer as summary for now
            summary = state.get("aggregated_query") or state.get("question", "")
            
            await PersistenceManager.archive_session(
                session_id=session_id,
                user_id=str(user_id),
                outcome=outcome,
                summary=summary,
                metrics=metrics
            )
            
            # 3. Save Searchable Summary
            if answer:
                await PersistenceManager.save_session_summary(
                    session_id=session_id,
                    summary_text=f"Q: {summary}\nA: {answer}",
                    tags=list(state.get("extracted_entities", {}).keys())
                )
        except Exception as e:
            print(f"⚠️ Error archiving session: {e}")

        return {}

# Singleton instance
archive_session_node = ArchiveSessionNode()
