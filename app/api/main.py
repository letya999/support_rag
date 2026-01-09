from fastapi import APIRouter
from . import rag_routes, config_routes, document_routes, metadata_routes, admin_routes

router = APIRouter()
router.include_router(rag_routes.router, tags=["RAG"])
router.include_router(config_routes.router, prefix="/config", tags=["Config"])
router.include_router(document_routes.router, prefix="/documents", tags=["Documents"])
router.include_router(metadata_routes.router, prefix="/documents/metadata-generation", tags=["Metadata"])
router.include_router(admin_routes.router, tags=["Admin"])
