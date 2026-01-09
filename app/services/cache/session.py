"""
Session Manager: Manages user sessions in Redis.

Refactored from app/cache/session_manager.py to follow services pattern.
"""

import json
import time
from typing import Optional
from redis.asyncio import Redis
from app.services.cache.models import UserSession
from app.pipeline.config_proxy import conversation_config


class SessionManager:
    """
    Manages user sessions in Redis.
    """
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.ttl = conversation_config.session_ttl_hours * 3600
        self.prefix = "session:"

    async def get_session(self, user_id: str, session_id: str = None) -> Optional[UserSession]:
        """
        Get active session for user. If session_id provided, verifies match.
        """
        # Strategy: we might store "session:user_id" -> session_data (if one active session per user allowed)
        # Or "session:session_id" -> session_data.
        # Let's assume unique session_id is the key, but we also want to know user's current session.
        # For simplicity in this MVP, we'll index by session_id if provided, 
        # OR we could have a "current_session:user_id" key pointing to session_id.
        
        # Current implementation: Key is "session:{session_id}"
        # If we only have user_id, we'd need a mapping "user:active_session:{user_id}" -> session_id
        
        if not session_id:
            # Try to find active session for user
            session_id = await self.redis.get(f"user:active_session:{user_id}")
            if not session_id:
                return None
            session_id = session_id.decode() if isinstance(session_id, bytes) else session_id

        key = f"{self.prefix}{session_id}"
        data = await self.redis.get(key)
        if not data:
            return None
            
        try:
            return UserSession.model_validate_json(data)
        except Exception as e:
            print(f"Error parsing session: {e}")
            return None

    async def create_session(self, user_id: str, session_id: str) -> UserSession:
        """
        Create a new session.
        """
        now = time.time()
        session = UserSession(
            user_id=user_id,
            session_id=session_id,
            start_time=now,
            last_activity_time=now,
            dialog_state="INITIAL"
        )
        
        await self.save_session(session)
        # Set active session pointer
        await self.redis.setex(
            f"user:active_session:{user_id}",
            self.ttl,
            session_id
        )
        return session

    async def save_session(self, session: UserSession):
        """
        Persist session state to Redis.
        """
        session.last_activity_time = time.time()
        key = f"{self.prefix}{session.session_id}"
        await self.redis.setex(
            key,
            self.ttl,
            session.model_dump_json()
        )
        # Refresh active pointer TTL
        await self.redis.expire(f"user:active_session:{session.user_id}", self.ttl)
        
    async def update_state(self, session_id: str, updates: dict):
        """
        Partial update of session state.
        """
        # This requires read-modify-write. 
        # Ideally use Lua script for atomicity but simple get-set is fine for MVP low concurrency for single user.
        # We need to fetch the session first since we only have session_id
        # We can't easily get the OBJECT without knowing the key. 
        # We know key is prefix + session_id.
        
        key = f"{self.prefix}{session_id}"
        data = await self.redis.get(key)
        if not data:
            return # Context lost or expired
            
        session = UserSession.model_validate_json(data)
        
        # Apply updates
        model_data = session.model_dump()
        model_data.update(updates)
        new_session = UserSession(**model_data)
        
        await self.save_session(new_session)

    async def clear_session(self, user_id: str):
        """
        Clear active session (on logout or expiration).
        """
        session_id = await self.redis.get(f"user:active_session:{user_id}")
        if session_id:
            session_id = session_id.decode() if isinstance(session_id, bytes) else session_id
            await self.redis.delete(f"{self.prefix}{session_id}")
        await self.redis.delete(f"user:active_session:{user_id}")
