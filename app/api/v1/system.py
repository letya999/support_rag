from fastapi import APIRouter, Request
from app.settings import settings
from app.api.v1.models import Envelope, MetaResponse
from typing import Dict

router = APIRouter(tags=["System"])

@router.get("/health", response_model=Envelope[Dict[str, str]])
async def health_check(request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    return Envelope(
        data={
            "status": "healthy",
            "database": "configured" if settings.DATABASE_URL else "missing",
            "redis": "configured" if settings.REDIS_URL else "missing",
            "llm": "configured" if settings.OPENAI_API_KEY else "missing"
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
