from fastapi import APIRouter
# from . import rag_routes, config_routes, document_routes, metadata_routes, admin_routes (Removed)

router = APIRouter()

# V1 API
from app.api.v1.router import api_router as v1_router
router.include_router(v1_router, prefix="/api/v1")

# Legacy Routes
# Legacy Routes have been removed
