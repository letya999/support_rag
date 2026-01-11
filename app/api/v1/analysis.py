from fastapi import APIRouter, HTTPException, Request, Path
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import psycopg
from app.api.v1.models import Envelope, MetaResponse
from app.services.classification.semantic_service import SemanticClassificationService
from app.settings import settings
from app.storage.qdrant_client import get_async_qdrant_client
from qdrant_client.http import models
import logging

router = APIRouter(tags=["Intelligence"])
logger = logging.getLogger(__name__)

# Models
class ClassificationResult(BaseModel):
    document_id: str
    intent: Optional[str]
    intent_confidence: float
    category: Optional[str]
    category_confidence: float

class MetadataUpdate(BaseModel):
    document_id: str
    metadata: Dict[str, Any]

# Endpoints

@router.post("/analysis/classify/{document_id}", response_model=Envelope[ClassificationResult])
async def classify_document(request: Request, document_id: int): # ID is serial int in DB
    """
    Auto-classify a document (chunk) by ID.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    # 1. Fetch content
    content = None
    if not settings.DATABASE_URL:
        raise HTTPException(status_code=500, detail="DB URL not set")
        
    async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT content FROM documents WHERE id = %s", (document_id,))
            row = await cur.fetchone()
            if row:
                content = row[0]
                
    if not content:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # 2. Classify
    service = SemanticClassificationService()
    result = await service.classify(content)
    
    if not result:
        raise HTTPException(status_code=500, detail="Classification failed")
        
    data = ClassificationResult(
        document_id=str(document_id),
        intent=result.intent,
        intent_confidence=result.intent_confidence,
        category=result.category,
        category_confidence=result.category_confidence
    )
    
    return Envelope(data=data, meta=MetaResponse(trace_id=trace_id))

@router.post("/analysis/metadata", response_model=Envelope[Dict[str, str]])
async def save_metadata(request: Request, body: MetadataUpdate):
    """
    Save/Overwrite metadata for a document.
    """
    trace_id = getattr(request.state, "trace_id", None)
    doc_id = int(body.document_id)
    
    # 1. Update DB
    if not settings.DATABASE_URL:
        raise HTTPException(status_code=500, detail="DB URL not set")

    async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
        async with conn.cursor() as cur:
            # We merge new metadata with existing or overwrite?
            # Plan says "Save results", "Touch-up".
            # usually merge is safer or JSONB update.
            # We'll do a merge logic (||)
            await cur.execute("""
                UPDATE documents 
                SET metadata = metadata || %s::jsonb 
                WHERE id = %s
            """, (import_json(body.metadata), doc_id))
            
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Document not found")

    # 2. Update Qdrant
    try:
        qdrant = get_async_qdrant_client()
        # Set payload by ID
        await qdrant.set_payload(
            collection_name="documents",
            payload=body.metadata,
            points=[doc_id]
        )
    except Exception as e:
        logger.error(f"Qdrant update failed: {e}")
        # Soft fail?
        
    return Envelope(
        data={"status": "updated", "document_id": str(doc_id)},
        meta=MetaResponse(trace_id=trace_id)
    )

@router.patch("/analysis/chunks/metadata", response_model=Envelope[Dict[str, str]])
async def patch_chunk_metadata(request: Request, body: MetadataUpdate):
    """
    Same as save_metadata but semantically for 'chunks'.
    """
    return await save_metadata(request, body)

import json
def import_json(d):
    return json.dumps(d)
