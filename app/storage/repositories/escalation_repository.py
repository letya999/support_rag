from app.storage.connection import get_db_connection

class EscalationRepository:
    """Repository for escalation events."""

    @staticmethod
    async def save_escalation(session_id: str, reason: str, priority: str = "normal"):
        """Record escalation event."""
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
