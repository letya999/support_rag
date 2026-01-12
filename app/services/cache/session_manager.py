"""
Session Manager: Manages user sessions in Redis.

Refactored from app/cache/session_manager.py to follow services pattern.
"""

import json
import time
from typing import Optional
from redis.asyncio import Redis
from app.services.cache.models import UserSession
from app.services.config_loader.conversation_config import conversation_config


class SessionManager:
    """
    Manages user sessions in Redis.
    """
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.ttl = int(conversation_config.session_ttl_hours * 3600)
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
        
        # Retry mechanism for saving session
        for attempt in range(3):
            try:
                await self.save_session(new_session)
                break
            except Exception as e:
                if attempt == 2:
                    print(f"❌ Failed to save session state after 3 attempts: {e}")
                else:
                    import asyncio
                    await asyncio.sleep(0.1)

    async def add_message(self, session_id: str, role: str, content: str):
        """
        Add a message to the recent_messages list in the session.
        Keeps strictly the last 50 messages to avoid bloating Redis.
        """
        key = f"{self.prefix}{session_id}"
        data = await self.redis.get(key)
        if not data:
            return

        try:
            session = UserSession.model_validate_json(data)
            
            # Add new message
            new_msg = {"role": role, "content": content}
            session.recent_messages.append(new_msg)
            
            # Trim if too long (keep last 50)
            if len(session.recent_messages) > 50:
                session.recent_messages = session.recent_messages[-50:]
                
            session.message_count += 1
            
            await self.save_session(session)
        except Exception as e:
            print(f"Failed to add message to cache: {e}")

    async def clear_session(self, user_id: str):
        """
        Clear active session (on logout or expiration).
        """
        session_id = await self.redis.get(f"user:active_session:{user_id}")
        if session_id:
            session_id = session_id.decode() if isinstance(session_id, bytes) else session_id
            await self.redis.delete(f"{self.prefix}{session_id}")
        await self.redis.delete(f"user:active_session:{user_id}")
