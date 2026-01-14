import json
from typing import List, Dict, Any
from app.storage.connection import get_db_connection

class MessageRepository:
    """Repository for message storage and retrieval."""

    @staticmethod
    async def save_message(
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: dict = None
    ):
        """Save a single message to DB."""
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO messages (session_id, user_id, role, content, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (session_id, user_id, role, content, json.dumps(metadata or {}))
                )

    @staticmethod
    async def get_session_messages(
        session_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Load message history for a session."""
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT session_id, role, content, created_at, metadata
                    FROM messages
                    WHERE session_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (session_id, limit)
                )
                rows = await cur.fetchall()
                
                # Reverse to get chronological order (oldest -> newest) of the recent slice
                rows.reverse()
                
                return [
                    {
                        "session_id": row[0],
                        "role": row[1],
                        "content": row[2],
                        "created_at": row[3].isoformat() if row[3] else None,
                        "metadata": row[4] or {}
                    }
                    for row in rows
                ]

    @staticmethod
    async def get_user_recent_messages(
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Load recent message history for a user across ALL sessions.
        
        Used for cross-session conversation context when user starts new session
        but needs historical context from previous conversations.
        
        Args:
            user_id: User identifier
            limit: Maximum messages to retrieve
        
        Returns:
            List of message dicts with session_id, role, content, created_at, and metadata
        """
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT session_id, role, content, created_at, metadata
                    FROM messages
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit)
                )
                rows = await cur.fetchall()
                
                # Reverse to get chronological order (oldest -> newest) of the recent slice
                rows.reverse()
                
                return [
                    {
                        "session_id": row[0],
                        "role": row[1],
                        "content": row[2],
                        "created_at": row[3].isoformat() if row[3] else None,
                        "metadata": row[4] or {}
                    }
                    for row in rows
                ]
