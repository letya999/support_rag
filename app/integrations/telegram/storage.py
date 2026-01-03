"""
Session Storage

Redis-based session storage for Telegram users.
"""

import json
import logging
import redis.asyncio as redis
from datetime import datetime
from typing import Optional, List

from app.integrations.telegram.models import UserSession, Message, MessageRole

logger = logging.getLogger(__name__)


class SessionStorage:
    """
    Redis-based storage for user sessions.

    Key format: user:{user_id}
    TTL: 24 hours
    """

    def __init__(self, redis_url: str):
        """
        Initialize storage with Redis URL.

        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379")
        """
        self.redis_url = redis_url
        self.redis: Optional[redis.Redis] = None
        self.SESSION_TTL = 24 * 60 * 60  # 24 hours

    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = await redis.from_url(self.redis_url)
            await self.redis.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")

    async def get_session(self, user_id: int) -> Optional[UserSession]:
        """
        Get user session from Redis.

        Args:
            user_id: Telegram user ID

        Returns:
            UserSession or None if not found
        """
        try:
            data = await self.redis.get(f"user:{user_id}")
            if not data:
                return None

            session_dict = json.loads(data)

            # Deserialize Message objects
            messages = [
                Message(
                    role=MessageRole(msg["role"]),
                    content=msg["content"],
                    timestamp=datetime.fromisoformat(msg["timestamp"]),
                    query_id=msg.get("query_id")
                )
                for msg in session_dict.get("messages", [])
            ]

            session_dict["messages"] = messages
            session_dict["created_at"] = datetime.fromisoformat(session_dict["created_at"])
            session_dict["last_activity"] = datetime.fromisoformat(session_dict["last_activity"])

            return UserSession(**session_dict)
        except Exception as e:
            logger.error(f"Error getting session for user {user_id}: {e}")
            return None

    async def save_session(self, session: UserSession):
        """
        Save user session to Redis.

        Args:
            session: UserSession object to save
        """
        try:
            session_dict = {
                "user_id": session.user_id,
                "username": session.username,
                "messages": [
                    {
                        "role": msg.role.value,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "query_id": msg.query_id
                    }
                    for msg in session.messages
                ],
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "is_active": session.is_active
            }

            await self.redis.setex(
                f"user:{session.user_id}",
                self.SESSION_TTL,
                json.dumps(session_dict)
            )
            logger.debug(f"Session saved for user {session.user_id}")
        except Exception as e:
            logger.error(f"Error saving session for user {session.user_id}: {e}")
            raise

    async def add_message(
        self,
        user_id: int,
        role: MessageRole,
        content: str,
        query_id: Optional[str] = None
    ):
        """
        Add message to user's conversation history.

        Args:
            user_id: Telegram user ID
            role: Message role (user or assistant)
            content: Message content
            query_id: Optional RAG pipeline query ID for tracking
        """
        try:
            session = await self.get_session(user_id)
            if not session:
                raise ValueError(f"Session not found for user {user_id}")

            message = Message(
                role=role,
                content=content,
                timestamp=datetime.now(),
                query_id=query_id
            )
            session.messages.append(message)
            session.last_activity = datetime.now()

            await self.save_session(session)
            logger.debug(f"Message added to user {user_id}: {role}")
        except Exception as e:
            logger.error(f"Error adding message for user {user_id}: {e}")
            raise

    async def clear_session(self, user_id: int):
        """
        Clear conversation history but keep session active.

        Args:
            user_id: Telegram user ID
        """
        try:
            session = await self.get_session(user_id)
            if session:
                session.messages = []
                session.last_activity = datetime.now()
                await self.save_session(session)
                logger.info(f"Session cleared for user {user_id}")
        except Exception as e:
            logger.error(f"Error clearing session for user {user_id}: {e}")
            raise

    async def delete_session(self, user_id: int):
        """
        Completely delete user session.

        Args:
            user_id: Telegram user ID
        """
        try:
            await self.redis.delete(f"user:{user_id}")
            logger.info(f"Session deleted for user {user_id}")
        except Exception as e:
            logger.error(f"Error deleting session for user {user_id}: {e}")
            raise

    async def get_session_context(
        self,
        user_id: int,
        max_messages: int = 6
    ) -> List[dict]:
        """
        Get recent messages for RAG pipeline context.

        Returns last N messages in format expected by RAG pipeline:
        [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]

        Args:
            user_id: Telegram user ID
            max_messages: Maximum number of messages to return

        Returns:
            List of message dicts with role and content
        """
        try:
            session = await self.get_session(user_id)
            if not session:
                return []

            # Get last N messages (excluding the current one)
            messages = session.messages[-(max_messages):]

            return [
                {
                    "role": msg.role.value,
                    "content": msg.content
                }
                for msg in messages
            ]
        except Exception as e:
            logger.error(f"Error getting session context for user {user_id}: {e}")
            return []
