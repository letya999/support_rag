import json
from typing import Dict, Any, Optional
from psycopg.rows import dict_row
from app.storage.connection import get_db_connection

class IdentityRepository:
    """Repository for managing user identities and metadata in the DB."""

    @staticmethod
    async def get_identity(identity_type: str, identity_value: str) -> Optional[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT user_id, metadata 
                    FROM user_identities 
                    WHERE identity_type = %s AND identity_value = %s
                    """,
                    (identity_type, identity_value)
                )
                return await cur.fetchone()

    @staticmethod
    async def update_identity_metadata(identity_type: str, identity_value: str, metadata: Dict[str, Any]):
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE user_identities 
                    SET last_seen = NOW(), metadata = %s
                    WHERE identity_type = %s AND identity_value = %s
                    """,
                    (json.dumps(metadata), identity_type, identity_value)
                )

    @staticmethod
    async def create_new_user_with_identity(
        user_id: str, 
        name: Optional[str], 
        identity_type: str, 
        identity_value: str, 
        metadata: Dict[str, Any]
    ):
        """Creates both the base user profile and the identity link atomically."""
        async with get_db_connection() as conn:
            # Note: Ideally this should be a transaction if your connection logic supports it globally,
            # but here we execute statements sequentially within the connection block.
            async with conn.cursor() as cur:
                # 1. Create Profile
                await cur.execute(
                    """
                    INSERT INTO user_profiles (user_id, name, created_at, last_seen)
                    VALUES (%s, %s, NOW(), NOW())
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (user_id, name)
                )
                # 2. Create Identity
                await cur.execute(
                    """
                    INSERT INTO user_identities (user_id, identity_type, identity_value, metadata, created_at, last_seen)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                    """,
                    (user_id, identity_type, identity_value, json.dumps(metadata))
                )
