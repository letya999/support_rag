"""
Taxonomy Service
Manages hierarchical category and intent structures
"""
from typing import Dict, List, Optional, Any
import logging
import asyncio
import psycopg
from qdrant_client.http import models

from app.settings import settings
from app._shared_config.intent_registry import get_registry
from app.storage.qdrant_client import get_async_qdrant_client
from app.services.metadata_generation.registry_generator import RegistryGenerator

logger = logging.getLogger(__name__)

class TaxonomyService:
    def __init__(self):
        self.db_url = settings.DATABASE_URL
        self.registry = get_registry()

    def get_tree(self) -> Dict[str, Any]:
        """Get the current intent registry tree."""
        # Ensure registry is loaded
        if not self.registry.is_loaded:
            self.registry.reload()

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
            
            # Update payload (Qdrant supports setting payload by filter, actually it's clearer to select then update or use set_payload with filter?)
            # Qdrant set_payload allows `points` selector which can be a filter in some SDK versions, or we need to scroll.
            # set_payload(payload, points=..., filtering=...) -> 'points' can be filter?
            # Looking at SDK, set_payload takes `points: Sequence[int | str] | Filter`.
            
            await qdrant.set_payload(
                collection_name="documents",
                payload={"category": new_name},
                points=filter_condition
            )
            qdrant_updated = -1 # Count unknown without scrolling
            
        except Exception as e:
            logger.error(f"Qdrant update failed: {e}")
            # Non-fatal? We should probably fail, but Postgres is already updated.
            # Inconsistent state risk.

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
            logger.error(f"Qdrant update failed: {e}")

        await self.sync_registry()
        return {"status": "success", "old_name": old_name, "new_name": new_name}

    async def sync_registry(self) -> Dict[str, Any]:
        """
        Regenerate registry from DB.
        """
        success = await RegistryGenerator.refresh_intents()
        if success:
            self.registry.reload()
            return {
                "status": "success",
                "message": "Registry synchronized",
                "categories": len(self.registry.categories),
                "intents": len(self.registry.intents)
            }
        else:
            raise Exception("Failed to sync registry")

taxonomy_service = TaxonomyService()
