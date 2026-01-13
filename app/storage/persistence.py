"""
Persistence Layer Coordination.

Refactored to use granular repositories:
- app.storage.repositories.user_repository
- app.storage.repositories.message_repository
- app.storage.repositories.session_repository
- app.storage.repositories.escalation_repository

This class is maintained for backward compatibility and convenience.
"""
from typing import Optional, Dict, Any, List

from app.storage.repositories.user_repository import UserRepository
from app.storage.repositories.message_repository import MessageRepository
from app.storage.repositories.session_repository import SessionRepository
from app.storage.repositories.escalation_repository import EscalationRepository

class PersistenceManager:
    """
    Facade for database operations, delegating to specific repositories.
    Provides a unified interface for session, message, user, and escalation storage.
    """
    
    # User Operations
    @staticmethod
    async def load_long_term_memory(user_id: str) -> Dict[str, Any]:
        """
        Load long-term memory (facts, preferences) for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict containing user memory
        """
        return await UserRepository.load_long_term_memory(user_id)



    @staticmethod
    async def save_user_profile_update(user_id: str, memory_update: Dict[str, Any], name: Optional[str] = None):
        """
        Save an update to the user's long-term profile.

        Args:
            user_id: User identifier
            memory_update: New facts or preferences to add
            name: User's name (optional)
        """
        return await UserRepository.save_user_profile_update(user_id, memory_update, name)

    @staticmethod
    async def save_message(
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: dict = None
    ):
        """
        Save a message to the conversation history.

        Args:
            session_id: Session identifier
            user_id: User identifier
            role: Message role ('user' or 'assistant')
            content: Message body
            metadata: Additional metadata (optional)
        """
        return await MessageRepository.save_message(session_id, user_id, role, content, metadata)

    @staticmethod
    async def get_session_messages(session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent messages for a session.

        Args:
            session_id: Session identifier
            limit: Maximum messages to retrieve

        Returns:
            List of message dicts
        """
        return await MessageRepository.get_session_messages(session_id, limit)

    @staticmethod
    async def update_session(
        session_id: str, 
        user_id: str, 
        channel: str, 
        status: str, 
        metadata: dict = None
    ):
        """
        Create or update a session record.

        Args:
            session_id: Session identifier
            user_id: User identifier
            channel: Communication channel
            status: Session status ('active', 'escalated', 'closed')
            metadata: Additional metadata (optional)
        """
        return await SessionRepository.update_session(session_id, user_id, channel, status, metadata)

    @staticmethod
    async def get_user_recent_sessions(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent sessions for a user.

        Args:
            user_id: User identifier
            limit: Maximum sessions to retrieve

        Returns:
            List of session dicts
        """
        return await SessionRepository.get_user_recent_sessions(user_id, limit)

    @staticmethod
    async def save_escalation(session_id: str, reason: str, priority: str = "normal"):
        """
        Record an escalation to a human agent.

        Args:
            session_id: Session identifier
            reason: Reason for escalation
            priority: Escalation priority ('normal', 'high')
        """
        return await EscalationRepository.save_escalation(session_id, reason, priority)
