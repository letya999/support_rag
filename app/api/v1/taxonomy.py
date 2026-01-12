from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.api.v1.models import Envelope, MetaResponse
from app.services.taxonomy import taxonomy_service

router = APIRouter(tags=["Categories & Intents"])

class RenameRequest(BaseModel):
    old_name: str
    new_name: str
    type: str = Field(..., pattern="^(category|intent)$")

@router.get("/categories/tree", response_model=Envelope[Dict[str, Any]])
async def get_taxonomy_tree(request: Request):
    """
    Get category/intent tree.
    """
    trace_id = getattr(request.state, "trace_id", None)
    data = await taxonomy_service.get_tree()
    return Envelope(data=data, meta=MetaResponse(trace_id=trace_id))

@router.patch("/categories/rename", response_model=Envelope[Dict[str, Any]])
async def rename_taxonomy_item(request: Request, body: RenameRequest):
    """
    Rename category or intent.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    try:
        if body.type == "category":
            result = await taxonomy_service.rename_category(body.old_name, body.new_name)
        else:
            result = await taxonomy_service.rename_intent(body.old_name, body.new_name)
            
        return Envelope(data=result, meta=MetaResponse(trace_id=trace_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/categories/sync", response_model=Envelope[Dict[str, Any]])
async def sync_taxonomy(request: Request):
    """
    Sync registry with DB documents.
    """
    trace_id = getattr(request.state, "trace_id", None)
    try:
        result = await taxonomy_service.sync_registry()
        return Envelope(data=result, meta=MetaResponse(trace_id=trace_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
