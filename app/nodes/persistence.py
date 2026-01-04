import json
from typing import Optional, Dict, Any
from psycopg.rows import dict_row
from app.storage.connection import get_db_connection

class PersistenceManager:
    """
    Manages long-term memory and session archiving in Postgres.
    Uses raw SQL via psycopg.
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
    async def get_recent_sessions(user_id: str, limit: int = 5) -> list:
        """
        Get summaries of recent sessions for context.
        """
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT session_id, start_time, outcome, summary 
                    FROM sessions_archive 
                    WHERE user_id = %s 
                    ORDER BY start_time DESC 
                    LIMIT %s
                    """,
                    (user_id, limit)
                )
                sessions = await cur.fetchall()
                
                return [
                    {
                        "session_id": s['session_id'],
                        "date": s['start_time'].isoformat() if s['start_time'] else None,
                        "outcome": s['outcome'],
                        "summary": s['summary']
                    }
                    for s in sessions
                ]

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
    async def archive_session(
        session_id: str, 
        user_id: str, 
        outcome: str, 
        summary: str, 
        metrics: Dict[str, Any] = None,
        duration_seconds: float = None
    ):
        """
        Save session result to archive.
        """
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO sessions_archive (session_id, user_id, outcome, summary, metrics, duration_seconds, end_time)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (session_id) DO UPDATE SET
                        outcome = EXCLUDED.outcome,
                        summary = EXCLUDED.summary,
                        metrics = EXCLUDED.metrics,
                        duration_seconds = EXCLUDED.duration_seconds,
                        end_time = NOW()
                    """,
                    (session_id, user_id, outcome, summary, json.dumps(metrics or {}), duration_seconds)
                )

    @staticmethod
    async def save_session_summary(session_id: str, summary_text: str, tags: list = None):
        """
        Save/update searchable summary.
        """
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO session_summaries (session_id, summary_text, search_tags)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                        summary_text = EXCLUDED.summary_text,
                        search_tags = EXCLUDED.search_tags
                    """,
                    (session_id, summary_text, tags or [])
                )
