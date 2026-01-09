import json
from typing import List, Dict, Any
from app.storage.connection import get_db_connection

class SessionRepository:
    """Repository for session metadata and history."""

    @staticmethod
    async def update_session(
        session_id: str,
        user_id: str,
        channel: str,
        status: str,
        metadata: dict = None
    ):
        """Create or update session metadata."""
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                # Create session if doesn't exist
                await cur.execute(
                    """
                    INSERT INTO sessions (session_id, user_id, channel, status)
                    VALUES (%s, %s, %s, 'active')
                    ON CONFLICT (session_id) DO NOTHING
                    """,
                    (session_id, user_id, channel)
                )
                
                # Update status and metadata
                await cur.execute(
                    """
                    UPDATE sessions SET
                        status = %s,
                        end_time = NOW(),
                        metadata = %s::jsonb
                    WHERE session_id = %s
                    """,
                    (status, json.dumps(metadata or {}), session_id)
                )

    @staticmethod
    async def get_user_recent_sessions(
        user_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Load recent sessions for a user."""
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT s.session_id, s.start_time, s.status, s.metadata,
                           COUNT(m.id) as message_count
                    FROM sessions s
                    LEFT JOIN messages m ON s.session_id = m.session_id
                    WHERE s.user_id = %s AND s.status != 'active'
                    GROUP BY s.session_id, s.start_time, s.status, s.metadata
                    ORDER BY s.end_time DESC NULLS LAST
                    LIMIT %s
                    """,
                    (user_id, limit)
                )
                rows = await cur.fetchall()
                
                return [
                    {
                        "session_id": row[0],
                        "start_time": row[1].isoformat() if row[1] else None,
                        "status": row[2],
                        "metadata": row[3] or {},
                        "message_count": row[4]
                    }
                    for row in rows
                ]
