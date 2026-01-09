"""
FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

from app.settings import settings
from app.api.main import router
from app.api.admin_routes import router as admin_router
from app.api.exceptions import validation_exception_handler
from app.services.cache.manager import get_cache_manager
from app.services.config_loader.loader import get_cache_config
from app.services.warmup_service import WarmupService
from app.storage.connection import init_db_pool, close_db_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup and cleanup on shutdown."""
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
        
        # Initialize DB Pool
        await init_db_pool()
        print("✅ DB Pool initialized")
    except Exception as e:
        print(f"⚠️  Cache initialization warning: {e}")
    
    # Warmup Models (prevents first-request latency)
    print("🔥 Warming up models...")
    await WarmupService.warmup_all()

    yield

    # Cleanup
    print("🛑 Shutting down Support RAG Pipeline...")
    try:
        cache = await get_cache_manager()
        await cache.close()
        print("✅ Cache closed")
        
        await close_db_pool()
        print("✅ DB Pool closed")
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan
)

# Include routers
app.include_router(router)
app.include_router(admin_router)

# Exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Support RAG Pipeline API is running"}
