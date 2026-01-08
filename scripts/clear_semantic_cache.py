"""
Script to clear semantic cache in Qdrant.
Run this to remove invalid cached entries after cache logic updates.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from app.storage.qdrant_client import get_async_qdrant_client

SEMANTIC_CACHE_COLLECTION = "semantic_cache"


async def clear_semantic_cache():
    """Delete all entries from semantic cache collection."""
    try:
        client = get_async_qdrant_client()
        
        # Check if collection exists
        collections = await client.get_collections()
        exists = any(c.name == SEMANTIC_CACHE_COLLECTION for c in collections.collections)
        
        if not exists:
            print(f"⚠️  Collection '{SEMANTIC_CACHE_COLLECTION}' does not exist")
            return
        
        # Delete the entire collection and recreate it
        await client.delete_collection(collection_name=SEMANTIC_CACHE_COLLECTION)
        print(f"🧹 Cleared semantic cache collection: {SEMANTIC_CACHE_COLLECTION}")
        
        # Collection will be recreated on next cache check
        print("✅ Cache cleared successfully. Collection will be recreated on next use.")
        
    except Exception as e:
        print(f"❌ Error clearing cache: {e}")


if __name__ == "__main__":
    asyncio.run(clear_semantic_cache())
