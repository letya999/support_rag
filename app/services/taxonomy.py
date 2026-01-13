"""
Taxonomy Service
Manages hierarchical category and intent structures
"""
from typing import Dict, List, Optional, Any
from app.settings import settings
from app._shared_config.intent_registry import get_registry
from app.storage.qdrant_client import get_async_qdrant_client
from app.logging_config import logger

import asyncio
import psycopg
from qdrant_client.http import models
from datetime import datetime

class TaxonomyService:
    """Service for managing the taxonomy (categories and intents) across storage backends."""
    def __init__(self):
        """Initialize TaxonomyService with database URL and registry."""
        self.db_url = settings.DATABASE_URL
        self.registry = get_registry()

    async def get_tree(self) -> Dict[str, Any]:
        """
        Get the current intent registry tree directly from DB (via IntentRegistryService).
        """
        # Ensure registry is fresh or loaded
        if not self.registry.is_loaded:
            await self.registry.initialize()

        return {
            "metadata": self.registry.metadata,
            "categories": [
                {
                    "name": cat,
                    "description": self.registry.get_category_description(cat),
                    "intents": self.registry.get_intents_for_category(cat)
                }
                for cat in self.registry.categories
            ]
        }
    
    async def rename_category(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """
        Rename a category in both Postgres and Qdrant.
        Trigger registry refresh.

        Args:
            old_name: Current category name
            new_name: New category name

        Returns:
            Dict with update status and statistics
        """
        if not self.db_url:
            raise ValueError("Database URL not configured")

        if old_name == new_name:
            return {"status": "skipped", "message": "Old and new names are identical"}

        # 1. Update Postgres
        updated_rows = 0
        async with await psycopg.AsyncConnection.connect(self.db_url, autocommit=True) as conn:
            async with conn.cursor() as cur:
                # Update metadata->'category' where it matches old_name
                await cur.execute("""
                    UPDATE documents 
                    SET metadata = jsonb_set(metadata, '{category}', %s::jsonb) 
                    WHERE metadata->>'category' = %s
                """, (f'"{new_name}"', old_name))
                updated_rows = cur.rowcount

        # 2. Update Qdrant
        qdrant_updated = 0
        try:
            qdrant = get_async_qdrant_client()
            # Filter points with old category
            filter_condition = models.Filter(
                must=[
                    models.FieldCondition(
                        key="category",
                        match=models.MatchValue(value=old_name)
                    )
                ]
            )
            
            await qdrant.set_payload(
                collection_name="documents",
                payload={"category": new_name},
                points=filter_condition
            )
            qdrant_updated = -1 
            
        except Exception as e:
            logger.error("Qdrant category update failed", extra={"error": str(e), "old_name": old_name, "new_name": new_name})

        # 3. Trigger Sync
        await self.sync_registry()

        return {
            "status": "success", 
            "updated_documents": updated_rows,
            "qdrant_updated": "filter_applied",
            "old_name": old_name, 
            "new_name": new_name
        }

    async def rename_intent(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """
        Rename an intent in both Postgres and Qdrant.

        Args:
            old_name: Current intent name
            new_name: New intent name

        Returns:
            Dict with update status
        """
        if not self.db_url:
            raise ValueError("Database URL not configured")

        async with await psycopg.AsyncConnection.connect(self.db_url, autocommit=True) as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE documents 
                    SET metadata = jsonb_set(metadata, '{intent}', %s::jsonb) 
                    WHERE metadata->>'intent' = %s
                """, (f'"{new_name}"', old_name))

        try:
            qdrant = get_async_qdrant_client()
            filter_condition = models.Filter(
                must=[
                    models.FieldCondition(
                        key="intent",
                        match=models.MatchValue(value=old_name)
                    )
                ]
            )
            await qdrant.set_payload(
                collection_name="documents",
                payload={"intent": new_name},
                points=filter_condition
            )
        except Exception as e:
            logger.error("Qdrant intent update failed", extra={"error": str(e), "old_name": old_name, "new_name": new_name})

        await self.sync_registry()
        return {"status": "success", "old_name": old_name, "new_name": new_name}


    async def get_all_categories(self) -> List[Dict[str, Any]]:
        """
        Get all unique categories from the database.
        Returns list of dicts with 'id' and 'name' fields.
        """
        if not self.db_url:
            raise ValueError("Database URL not configured")
        
        async with await psycopg.AsyncConnection.connect(self.db_url) as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT DISTINCT 
                        ROW_NUMBER() OVER (ORDER BY metadata->>'category') as id,
                        metadata->>'category' as name
                    FROM documents 
                    WHERE metadata->>'category' IS NOT NULL
                    ORDER BY name
                """)
                rows = await cur.fetchall()
                return [{"id": row[0], "name": row[1]} for row in rows]
    
    async def get_intents_by_category(self, category_id: int = None, category_name: str = None) -> List[Dict[str, Any]]:
        """
        Get all intents for a specific category.
        Can filter by category_id (row number) or category_name.
        Returns list of dicts with 'id' and 'name' fields.
        """
        if not self.db_url:
            raise ValueError("Database URL not configured")
        
        # If category_id provided, first get category name
        if category_id is not None and category_name is None:
            categories = await self.get_all_categories()
            matching = [c for c in categories if c["id"] == category_id]
            if not matching:
                return []
            category_name = matching[0]["name"]
        
        if category_name is None:
            raise ValueError("Either category_id or category_name must be provided")
        
        async with await psycopg.AsyncConnection.connect(self.db_url) as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT DISTINCT 
                        ROW_NUMBER() OVER (ORDER BY metadata->>'intent') as id,
                        metadata->>'intent' as name
                    FROM documents 
                    WHERE metadata->>'category' = %s
                    AND metadata->>'intent' IS NOT NULL
                    ORDER BY name
                """, (category_name,))
                rows = await cur.fetchall()
                return [{"id": row[0], "name": row[1]} for row in rows]

    async def sync_registry(self) -> Dict[str, Any]:

        """
        Refresh registry from DB.
        """
        success = await self.registry.reload()
        if success:
            return {
                "status": "success",
                "message": "Registry synchronized from DB",
                "categories": len(self.registry.categories),
                "intents": len(self.registry.intents)
            }
        else:
            raise Exception("Failed to sync registry")

taxonomy_service = TaxonomyService()
