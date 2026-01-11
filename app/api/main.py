from fastapi import APIRouter
from . import rag_routes, config_routes, document_routes, metadata_routes, admin_routes

router = APIRouter()

# V1 API
from app.api.v1.router import api_router as v1_router
router.include_router(v1_router, prefix="/api/v1")

# Legacy Routes
router.include_router(rag_routes.router, tags=["RAG (Legacy)"])
router.include_router(config_routes.router, prefix="/config", tags=["Config (Legacy)"])
router.include_router(document_routes.router, prefix="/documents", tags=["Documents (Legacy)"])
router.include_router(metadata_routes.router, prefix="/documents/metadata-generation", tags=["Metadata (Legacy)"])
router.include_router(admin_routes.router, tags=["Admin (Legacy)"])
