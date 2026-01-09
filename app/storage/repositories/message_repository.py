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
                    SELECT role, content, created_at, metadata
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
                        "role": row[0],
                        "content": row[1],
                        "created_at": row[2].isoformat() if row[2] else None,
                        "metadata": row[3] or {}
                    }
                    for row in rows
                ]
