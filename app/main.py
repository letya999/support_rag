"""
FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

from app.settings import settings
from app.api.main import router
# from app.api.admin_routes import router as admin_router
# Use V1 handlers for global consistency
from app.api.v1.middleware import RequestIDMiddleware, validation_exception_handler, global_exception_handler
from app.api.v1.limiter import init_limiter
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
        
        # Initialize Rate Limiter
        await init_limiter()
        print("✅ Rate Limiter initialized")
        
        # Initialize DB Pool
        await init_db_pool()
        print("✅ DB Pool initialized")
    except Exception as e:
        print(f"⚠️  Cache/DB initialization warning: {e}")
    
    # Warmup Models (prevents first-request latency)
    print("🔥 Warming up models...")
    from app._shared_config.intent_registry import get_registry
    await get_registry().initialize()
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


from fastapi.openapi.utils import get_openapi

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.APP_NAME,
        version="1.0.0",
        description="""
### Support RAG Engine API

This is the core API for the Support RAG system, handling:
- **Chat & RAG**: Intelligent question answering with context.
- **Channels**: Integration with Telegram and other messaging platforms.
- **Knowledge Base**: Management of documents, drafts, and embeddings.
- **Intelligence**: Auto-classification and taxonomy management.
- **System**: Health checks and configuration.

All endpoints under `/api/v1` return standardized `Envelope` responses.
        """,
        routes=app.routes,
    )
    
    # Custom logo or extra info could go here
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Middleware
app.add_middleware(RequestIDMiddleware)

# Include routers
app.include_router(router)
from app.api.asyncapi_gen import router as asyncapi_router
app.include_router(asyncapi_router)
# app.include_router(admin_router)


# Exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Support RAG Pipeline API is running"}
