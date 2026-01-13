from fastapi import APIRouter, Request
from app.settings import settings
from app.api.v1.models import Envelope, MetaResponse
from typing import Dict

router = APIRouter(tags=["System"])

@router.get("/health", response_model=Envelope[Dict[str, str]])
async def health_check(request: Request):
    """
    Basic health check endpoint.

    For detailed system status, use internal monitoring tools.
    This endpoint intentionally provides minimal information to prevent
    information disclosure to potential attackers.
    """
    trace_id = getattr(request.state, "trace_id", None)

    # Simple health check - only report if system is up
    # Don't expose configuration details for security
    return Envelope(
        data={
            "status": "healthy",
            "version": "1.0.0"
        },
        meta=MetaResponse(trace_id=trace_id)
    )

@router.get("/ping", response_model=Envelope[str])
async def ping(request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return Envelope(
        data="pong",
        meta=MetaResponse(trace_id=trace_id)
    )
