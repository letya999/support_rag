"""
State Manager: Business logic for conversation state management.

Handles high-level session lifecycle and state transitions, delegating 
storage to SessionManager (Redis).
"""
from typing import Optional, Dict, Any
from app.services.cache.session_manager import SessionManager
from app.services.cache.models import UserSession

class StateManager:
    """
    Manages the lifecycle and state transitions of user conversations.
    """
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def start_session(self, user_id: str, session_id: str) -> UserSession:
        """
        Start a new conversation session.
        Initializes state to INITIAL and sets up tracking.
        """
        # We could add logic here to check if active session exists and archive it?
        # For now, just create new.
        return await self.session_manager.create_session(user_id, session_id)

    async def get_active_session(self, user_id: str) -> Optional[UserSession]:
        """Get the currently active session for the user."""
        return await self.session_manager.get_session(user_id)

    async def get_active_state(self, user_id: str) -> Optional[str]:
        """Get current dialog state for user."""
        session = await self.get_active_session(user_id)
        if session:
            return session.dialog_state
        return None

    async def update_dialog_state(self, session_id: str, new_state: str, context: Dict[str, Any] = None):
        """
        Transition the dialog state.
        
        Args:
            session_id: The session ID
            new_state: The target state (e.g., "ANSWER_PROVIDED")
            context: Additional context updates (attempt_count, entities, etc.)
        """
        # Potential future validation: Check if transition is valid using RulesEngine?
        # For now, we trust the caller (StateMachineNode).
        
        updates = {"dialog_state": new_state}
        if context:
            # Update specific fields if provided
            if "attempt_count" in context:
                updates["attempt_count"] = context["attempt_count"]
            if "extracted_entities" in context:
                updates["extracted_entities"] = context["extracted_entities"]
        
        await self.session_manager.update_state(session_id, updates)

    async def close_session(self, user_id: str):
        """End the current session."""
        await self.session_manager.clear_session(user_id)
