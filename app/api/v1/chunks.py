
from fastapi import APIRouter, HTTPException, Request, Query, Path, Body
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from app.api.v1.models import Envelope, MetaResponse, PaginationMeta
from app.services.chunk_service import chunk_service
import logging

router = APIRouter(tags=["Chunks"])
logger = logging.getLogger(__name__)

# --- Models ---

class ChunkMetadata(BaseModel):
    # Flexible metadata, but we can document known fields if we want.
    # For now, allow generic Dict to match existing loose schema.
    intent: Optional[str] = None
    category: Optional[str] = None
    source_document: Optional[str] = None
    extraction_date: Optional[str] = None
    requires_handoff: Optional[bool] = None
    # Allow other fields
    class Config:
        extra = "allow"

class ChunkResponse(BaseModel):
    id: int
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ChunkUpdate(BaseModel):
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ChunkListResponse(BaseModel):
    items: List[ChunkResponse]
    total: int
    page: int
    size: int

# --- Endpoints ---

@router.get("/chunks", response_model=Envelope[List[ChunkResponse]])
async def list_chunks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    chunk_id: Optional[int] = None,
    intent: Optional[str] = None,
    category: Optional[str] = None,
    source_document: Optional[str] = None,
    requires_handoff: Optional[bool] = None,
    extraction_date: Optional[str] = None
):
    """
    Search and filter chunks (documents) in the database.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    result = await chunk_service.list_chunks(
        page=page,
        page_size=size,
        search=search,
        chunk_id=chunk_id,
        intent=intent,
        category=category,
        source_document=source_document,
        requires_handoff=requires_handoff,
        extraction_date=extraction_date
    )
    
    pagination = PaginationMeta(
        limit=result["size"],
        offset=(result["page"] - 1) * result["size"],
        total=result["total"]
    )
    
    # Map raw dicts to Pydantic models (fastapi does this auto but explicit is good)
    return Envelope(
        data=result["items"],
        meta=MetaResponse(trace_id=trace_id, pagination=pagination)
    )

@router.get("/chunks/{chunk_id}", response_model=Envelope[ChunkResponse])
async def get_chunk(
    request: Request,
    chunk_id: int = Path(...)
):
    """
    Get a specific chunk by ID.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    chunk = await chunk_service.get_chunk(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
        
    return Envelope(
        data=chunk,
        meta=MetaResponse(trace_id=trace_id)
    )

@router.patch("/chunks/{chunk_id}", response_model=Envelope[ChunkResponse])
async def update_chunk(
    request: Request,
    chunk_id: int = Path(...),
    body: ChunkUpdate = Body(...)
):
    """
    Update a chunk's content or metadata.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    updated_chunk = await chunk_service.update_chunk(
        chunk_id=chunk_id,
        content=body.content,
        metadata=body.metadata
    )
    
    if not updated_chunk:
        # Check if it didn't exist
        existing = await chunk_service.get_chunk(chunk_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Chunk not found")
        # If it existed but no update made, just return existing
        updated_chunk = existing
        
    return Envelope(
        data=updated_chunk,
        meta=MetaResponse(trace_id=trace_id)
    )

@router.delete("/chunks/{chunk_id}", response_model=Envelope[Dict[str, Any]])
async def delete_chunk(
    request: Request,
    chunk_id: int = Path(...)
):
    """
    Delete a chunk from the database and vector store.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    success = await chunk_service.delete_chunk(chunk_id)
    if not success:
         raise HTTPException(status_code=404, detail="Chunk not found")
         
    return Envelope(
        data={"status": "deleted", "id": chunk_id},
        meta=MetaResponse(trace_id=trace_id)
    )
