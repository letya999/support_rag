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
    """
    
    # User Operations
    @staticmethod
    async def load_long_term_memory(user_id: str) -> Dict[str, Any]:
        return await UserRepository.load_long_term_memory(user_id)

    @staticmethod
    async def save_user_profile_update(user_id: str, memory_update: Dict[str, Any], name: Optional[str] = None):
        return await UserRepository.save_user_profile_update(user_id, memory_update, name)

    # Message Operations
    @staticmethod
    async def save_message(
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: dict = None
    ):
        return await MessageRepository.save_message(session_id, user_id, role, content, metadata)

    @staticmethod
    async def get_session_messages(session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        return await MessageRepository.get_session_messages(session_id, limit)

    # Session Operations
    @staticmethod
    async def update_session(
        session_id: str, 
        user_id: str, 
        channel: str, 
        status: str, 
        metadata: dict = None
    ):
        return await SessionRepository.update_session(session_id, user_id, channel, status, metadata)

    @staticmethod
    async def get_user_recent_sessions(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        return await SessionRepository.get_user_recent_sessions(user_id, limit)

    # Escalation Operations
    @staticmethod
    async def save_escalation(session_id: str, reason: str, priority: str = "normal"):
        return await EscalationRepository.save_escalation(session_id, reason, priority)
