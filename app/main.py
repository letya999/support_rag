from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.config.settings import settings
from app.api.routes import router
from app.api.exceptions import validation_exception_handler
from fastapi.exceptions import RequestValidationError
from app.cache.cache_layer import get_cache_manager


# Startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize cache on startup."""
    print("🚀 Starting Support RAG Pipeline...")

    # Initialize cache manager
    try:
        redis_url = settings.REDIS_URL if hasattr(settings, 'REDIS_URL') else "redis://localhost:6379/0"
        cache = await get_cache_manager(redis_url=redis_url)
        health = await cache.health_check()
        print(f"✅ Cache initialized: {health['backend'].upper()}")
    except Exception as e:
        print(f"⚠️  Cache initialization warning: {e}")

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
