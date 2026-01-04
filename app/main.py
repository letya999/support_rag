from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
from app.settings import settings
from app.api.routes import router
from app.api.exceptions import validation_exception_handler
from fastapi.exceptions import RequestValidationError
from app.cache.cache_layer import get_cache_manager
from app.services.config_loader.loader import get_cache_config
from app.nodes.reranking.ranker import get_reranker
from app.nodes.easy_classification.semantic_classifier import SemanticClassificationService
from app.integrations.embeddings import get_embedding


# Startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize cache on startup."""
    print("🚀 Starting Support RAG Pipeline...")

    # Initialize cache manager
    try:
        cache_params = get_cache_config()
        redis_url = cache_params.get("redis_url", settings.REDIS_URL)
        
        cache = await get_cache_manager(
            redis_url=redis_url,
            max_entries=cache_params.get("max_entries", 1000),
            ttl_seconds=cache_params.get("ttl_seconds", 86400)
        )
        health = await cache.health_check()
        print(f"✅ Cache initialized: {health['backend'].upper()}")
    except Exception as e:
        print(f"⚠️  Cache initialization warning: {e}")
    
    # Warmup Models (Background)
    print("🔥 Warming up models (Reranker, Classifier)...")
    
    async def warmup():
        loop = asyncio.get_running_loop()
        try:
            # 1. Reranker
            ranker = get_reranker()
            await loop.run_in_executor(None, ranker.rank, "warmup", ["warmup"])
            print("✅ Reranker Warmed Up")
            
            # 2. Classifier
            svc = SemanticClassificationService()
            await svc._ensure_model()
            print("✅ Classifier Warmed Up")

            # 3. Embeddings
            await get_embedding("warmup")
            print("✅ Embeddings Warmed Up")
        except Exception as e:
            print(f"⚠️ Warmup failed: {e}")

    # Fire and forget (or await if critical)
    asyncio.create_task(warmup())

    yield


    # Cleanup
    print("🛑 Shutting down Support RAG Pipeline...")
    try:
        cache = await get_cache_manager()
        await cache.close()
        print("✅ Cache closed")
    except Exception as e:
        print(f"⚠️  Cache cleanup warning: {e}")


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan
)

app.include_router(router)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


@app.get("/")
async def root():
    return {"message": "Support RAG Pipeline API is running"}


@app.get("/cache/status")
async def cache_status():
    """Get cache status and statistics."""
    from app.cache.cache_layer import get_cache_manager
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
