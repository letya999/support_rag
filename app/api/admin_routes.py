"""
Admin API routes for system management and diagnostics.
"""
from fastapi import APIRouter
from app.services.cache.manager import get_cache_manager
from app.nodes._shared_config.intent_registry import get_registry
from app.services.classification.semantic_service import SemanticClassificationService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/cache/status")
async def cache_status():
    """Get cache status and statistics."""
    try:
        cache = await get_cache_manager()
        health = await cache.health_check()
        stats = cache.get_stats()

        return {
            "health": health,
            "stats": stats.model_dump() if stats else None
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/refresh-intents")
async def refresh_intents():
    """
    Refresh the intents registry and reload classifier embeddings.
    
    This endpoint:
    1. Reloads the intents_registry.yaml file
    2. Updates the SemanticClassificationService embeddings
    
    Call this after running `python scripts/refresh_intents.py` to pick up
    changes without restarting the service.
    """
    try:
        # Reload registry from file
        registry = get_registry()
        registry.reload()
        
        # Refresh classifier embeddings
        classifier = SemanticClassificationService()
        success = await classifier.refresh_embeddings()
        
        if success:
            return {
                "status": "success",
                "message": "Intents registry and classifier embeddings refreshed",
                "categories": len(registry.categories),
                "intents": len(registry.intents),
                "metadata": registry.metadata
            }
        else:
            return {
                "status": "partial",
                "message": "Registry reloaded but classifier refresh failed (model not initialized)",
                "categories": len(registry.categories),
                "intents": len(registry.intents)
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/intents-registry")
async def get_intents_registry():
    """
    Get current state of the intents registry.
    
    Returns the loaded categories, intents, and metadata.
    """
    try:
        registry = get_registry()
        
        return {
            "status": "loaded" if registry.is_loaded else "not_loaded",
            "metadata": registry.metadata,
            "categories": [
                {
                    "name": cat,
                    "description": registry.get_category_description(cat),
                    "intents": registry.get_intents_for_category(cat)
                }
                for cat in registry.categories
            ],
            "total_categories": len(registry.categories),
            "total_intents": len(registry.intents)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
