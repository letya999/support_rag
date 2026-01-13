import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.storage.connection import get_db_connection

class WebhookRepository:
    """Repository for managing webhooks and their deliveries."""

    @staticmethod
    async def create_webhook(
        webhook_id: str,
        name: str,
        url: str,
        events: List[str],
        secret_hash: str,
        description: str = None,
        active: bool = True,
        metadata: Dict[str, Any] = None,
        ip_whitelist: List[str] = None
    ) -> Dict[str, Any]:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO webhooks (
                        webhook_id, name, url, events, secret_hash, 
                        description, active, metadata, ip_whitelist,
                        created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING *
                    """,
                    (
                        webhook_id, name, url, json.dumps(events), secret_hash,
                        description, active, json.dumps(metadata or {}),
                        json.dumps(ip_whitelist or [])
                    )
                )
                row = await cur.fetchone()
                # Assuming RowFactory acts like dict or we map it. 
                # Psycopg 3 returns tuple by default unless row_factory is set. 
                # Let's map it manually to be safe or use DictRow if configured.
                # Standard psycopg 3 returns tuples.
                return WebhookRepository._map_webhook_row(row, cur.description)

    @staticmethod
    async def get_webhook(webhook_id: str) -> Optional[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM webhooks WHERE webhook_id = %s",
                    (webhook_id,)
                )
                row = await cur.fetchone()
                if not row:
                    return None
                return WebhookRepository._map_webhook_row(row, cur.description)
    
    @staticmethod
    async def get_webhooks_by_event(event_type: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Find webhooks that subscribe to a specific event."""
        # This requires searching the JSON array.
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                sql = """
                    SELECT * FROM webhooks 
                    WHERE events::jsonb ? %s
                """
                if active_only:
                    sql += " AND active = TRUE"
                
                await cur.execute(sql, (event_type,))
                rows = await cur.fetchall()
                return [WebhookRepository._map_webhook_row(row, cur.description) for row in rows]

    @staticmethod
    async def list_webhooks(
        limit: int = 20, 
        offset: int = 0, 
        active: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                query = "SELECT * FROM webhooks"
                params = []
                
                if active is not None:
                    query += " WHERE active = %s"
                    params.append(active)
                
                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                await cur.execute(query, tuple(params))
                rows = await cur.fetchall()
                return [WebhookRepository._map_webhook_row(row, cur.description) for row in rows]

    @staticmethod
    async def update_webhook(
        webhook_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        # SECURITY: Use immutable set of allowed fields to prevent SQL injection
        # Column names cannot be parameterized in SQL, so we use a strict whitelist
        VALID_FIELDS = frozenset({
            'name', 'url', 'events', 'description',
            'active', 'metadata', 'ip_whitelist'
        })

        JSON_FIELDS = frozenset({'events', 'metadata', 'ip_whitelist'})

        # Filter and prepare updates - only allow whitelisted fields
        fields = []
        values = []
        for k, v in updates.items():
            # Double-check field is in whitelist
            if k not in VALID_FIELDS:
                # Skip invalid fields silently to prevent errors
                # In production, you might want to log this
                continue

            # Validate field name contains only alphanumeric and underscore
            # This is redundant given the whitelist, but defense in depth
            if not k.replace('_', '').isalnum():
                continue

            fields.append(f"{k} = %s")
            if k in JSON_FIELDS:
                values.append(json.dumps(v))
            else:
                values.append(v)

        if not fields:
            return await WebhookRepository.get_webhook(webhook_id)

        fields.append("updated_at = NOW()")
        values.append(webhook_id)  # for WHERE clause

        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                # Build query with validated field names
                query = f"""
                    UPDATE webhooks
                    SET {', '.join(fields)}
                    WHERE webhook_id = %s
                    RETURNING *
                """
                await cur.execute(query, tuple(values))
                row = await cur.fetchone()
                if not row:
                    return None
                return WebhookRepository._map_webhook_row(row, cur.description)

    @staticmethod
    async def delete_webhook(webhook_id: str) -> bool:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM webhooks WHERE webhook_id = %s",
                    (webhook_id,)
                )
                return cur.rowcount > 0

    @staticmethod
    async def log_delivery(
        delivery_id: str,
        webhook_id: str,
        event_id: str,
        event_type: str,
        payload: Dict[str, Any],
        status: str,
        attempt: int = 1,
        http_status: Optional[int] = None,
        error_message: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        next_retry: Optional[datetime] = None
    ):
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO webhook_deliveries (
                        delivery_id, webhook_id, event_id, event_type, payload,
                        status, http_status, attempt, error_message, 
                        response_time_ms, next_retry, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        delivery_id, webhook_id, event_id, event_type, json.dumps(payload),
                        status, http_status, attempt, error_message,
                        response_time_ms, next_retry
                    )
                )

    @staticmethod
    async def get_deliveries(
        webhook_id: str,
        limit: int = 20,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                query = "SELECT * FROM webhook_deliveries WHERE webhook_id = %s"
                params = [webhook_id]
                
                if status:
                    query += " AND status = %s"
                    params.append(status)
                
                query += " ORDER BY created_at DESC LIMIT %s"
                params.append(limit)
                
                await cur.execute(query, tuple(params))
                rows = await cur.fetchall()
                return [WebhookRepository._map_delivery_row(row, cur.description) for row in rows]

    @staticmethod
    async def get_delivery(delivery_id: str) -> Optional[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM webhook_deliveries WHERE delivery_id = %s",
                    (delivery_id,)
                )
                row = await cur.fetchone()
                if not row:
                    return None
                return WebhookRepository._map_delivery_row(row, cur.description)

    
    @staticmethod
    def _map_webhook_row(row, description) -> Dict[str, Any]:
        col_names = [desc.name for desc in description]
        return dict(zip(col_names, row))

    @staticmethod
    def _map_delivery_row(row, description) -> Dict[str, Any]:
        col_names = [desc.name for desc in description]
        return dict(zip(col_names, row))
