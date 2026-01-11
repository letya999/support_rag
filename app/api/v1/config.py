from fastapi import APIRouter, Request, HTTPException
from app.settings import settings
from app.api.v1.models import Envelope, MetaResponse
from typing import Dict, Any
from pathlib import Path
from app.services.config_loader.config_builder import PipelineConfigBuilder

router = APIRouter(tags=["Config"])

@router.get("/config/full", response_model=Envelope[Dict[str, Any]])
async def get_config(request: Request):
    """
    Get full config (masked).
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    # Mask secrets
    conf = settings.model_dump()
    masked = {}
    for k, v in conf.items():
        if "KEY" in k or "PASSWORD" in k or "SECRET" in k or "TOKEN" in k:
            masked[k] = "***"
        else:
            masked[k] = v
            
    return Envelope(data=masked, meta=MetaResponse(trace_id=trace_id))

@router.get("/config/phrases", response_model=Envelope[Dict[str, Any]])
async def get_phrases(request: Request):
    """
    Get system phrases.
    """
    trace_id = getattr(request.state, "trace_id", None)
    # Currently hardcoded or could be loaded from settings/yaml
    return Envelope(
        data={
            "welcome": "Привет! Я Support RAG бот.",
            "fallback": "К сожалению, я не нашел ответа в документах.",
            "escalate": "Перевожу на оператора."
        },
        meta=MetaResponse(trace_id=trace_id)
    )

@router.post("/config/refresh", response_model=Envelope[Dict[str, Any]])
async def refresh_pipeline_config(request: Request):
    """
    Regenerate pipeline_config.yaml from node configs.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    try:
        # Assuming app root is correct relative to this file?
        # Safe way: settings.BASE_DIR?
        # Or construct Path(__file__)....
        # We need project root.
        root_dir = Path(__file__).resolve().parent.parent.parent.parent
        builder = PipelineConfigBuilder(root_dir)
        config = builder.generate_full_config()
        
        return Envelope(
            data={"status": "refreshed", "nodes_count": len(config.get("details", {}))},
            meta=MetaResponse(trace_id=trace_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
