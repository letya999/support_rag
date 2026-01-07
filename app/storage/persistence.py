import json
from typing import Optional, Dict, Any, List
from psycopg.rows import dict_row
from app.storage.connection import get_db_connection

class PersistenceManager:
    """
    Manages long-term memory and session archiving in Postgres.
    Service layer for database access.
    """
    
    @staticmethod
    async def load_long_term_memory(user_id: str) -> Dict[str, Any]:
        """
        Load user profile and long-term memory.
        """
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT name, long_term_memory, last_seen FROM user_profiles WHERE user_id = %s",
                    (user_id,)
                )
                profile = await cur.fetchone()
                
                if profile:
                    return {
                        "exists": True,
                        "name": profile['name'],
                        "memory": profile['long_term_memory'],
                        "last_seen": profile['last_seen'].isoformat() if profile['last_seen'] else None
                    }
                else:
                    return {"exists": False}

    @staticmethod
    async def save_user_profile_update(user_id: str, memory_update: Dict[str, Any], name: Optional[str] = None):
        """
        Update or create user profile.
        """
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                # Check if exists
                await cur.execute(
                    "SELECT long_term_memory FROM user_profiles WHERE user_id = %s",
                    (user_id,)
                )
                existing = await cur.fetchone()
                
                if existing:
                    # Update
                    current_mem = existing['long_term_memory'] or {}
                    current_mem.update(memory_update)
                    
                    if name:
                        await cur.execute(
                            """
                            UPDATE user_profiles 
                            SET long_term_memory = %s, name = %s, last_seen = NOW() 
                            WHERE user_id = %s
                            """,
                            (json.dumps(current_mem), name, user_id)
                        )
                    else:
                        await cur.execute(
                            """
                            UPDATE user_profiles 
                            SET long_term_memory = %s, last_seen = NOW() 
                            WHERE user_id = %s
                            """,
                            (json.dumps(current_mem), user_id)
                        )
                else:
                    # Insert
                    await cur.execute(
                        """
                        INSERT INTO user_profiles (user_id, name, long_term_memory)
                        VALUES (%s, %s, %s)
                        """,
                        (user_id, name, json.dumps(memory_update))
                    )

    @staticmethod
    async def save_message(
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: dict = None
    ):
        """Save a single message to DB (New Schema)."""
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
    async def update_session(
        session_id: str,
        user_id: str,
        channel: str,
        status: str,
        metadata: dict = None
    ):
        """Create or update session metadata (New Schema)."""
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
    async def get_session_messages(
        session_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Load message history for a session (New Schema)."""
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

    @staticmethod
    async def get_user_recent_sessions(
        user_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Load recent sessions for a user (New Schema)."""
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

    @staticmethod
    async def save_escalation(session_id: str, reason: str, priority: str = "normal"):
        """Record escalation event (New Schema)."""
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO escalations (session_id, reason, priority, status)
                    VALUES (%s, %s, %s, 'pending')
                    ON CONFLICT (session_id) DO NOTHING
                    """,
                    (session_id, reason, priority)
                )
