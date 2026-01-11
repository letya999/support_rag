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

class DocumentSummary(BaseModel):
    document_id: int
    content_preview: str
    metadata: Dict[str, Any]

# Endpoints

@router.get("/analysis/documents", response_model=Envelope[List[DocumentSummary]])
async def list_documents(
    request: Request, 
    limit: int = 20, 
    offset: int = 0
):
    """
    List sample documents/chunks from the database.
    Useful for finding IDs to test classification.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    if not settings.DATABASE_URL:
        raise HTTPException(status_code=500, detail="DB URL not set")
        
    documents = []
    async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL, autocommit=True) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, content, metadata FROM documents ORDER BY id DESC LIMIT %s OFFSET %s", 
                (limit, offset)
            )
            rows = await cur.fetchall()
            
            for row in rows:
                doc_id, content, metadata = row
                # Truncate content for preview
                preview = content[:100] + "..." if len(content) > 100 else content
                
                documents.append(DocumentSummary(
                    document_id=doc_id,
                    content_preview=preview,
                    metadata=metadata or {}
                ))
    
    return Envelope(
        data=documents,
        meta=MetaResponse(
            trace_id=trace_id,
            pagination={
                "limit": limit,
                "offset": offset,
                "total": len(documents) # Approximation for now
            }
        )
    )

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

@router.post("/analysis/classify-draft/{draft_id}", response_model=Envelope[List[Dict[str, Any]]])
async def classify_draft(
    request: Request, 
    draft_id: str, 
    update_staging: bool = False
):
    """
    Classify/Cluster all chunks in a Staging Draft (Redis).
    Uses LLM-based Discovery to generate intents/categories dynamically (clustering).
    Results are applied directly to the chunk's metadata in the response.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    # 1. Fetch Draft
    from app.services.staging import staging_service
    draft = await staging_service.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    # 2. Process with Discovery Service (LLM Clustering)
    from app.services.classification.discovery_service import DiscoveryService
    service = DiscoveryService()
    
    chunks = draft.get("chunks", [])
    if not chunks:
        return Envelope(data=[], meta=MetaResponse(trace_id=trace_id))

    # Send only valid chunks with Q&A
    valid_chunks = [c for c in chunks if c.get("question") and c.get("answer")]
    
    predictions = await service.discover_intents(valid_chunks)
    
    # Map predictions by ID for easy lookup
    pred_map = {p.chunk_id: p for p in predictions}

    # 3. Format Results and Apply Updates
    results = []
    updates_for_staging = []
    
    for chunk in chunks:
        c_id = chunk.get("chunk_id")
        
        # Base object structure
        res_item = {
            "question": chunk.get("question"),
            "answer": chunk.get("answer"),
            "metadata": chunk.get("metadata", {}).copy() # Copy to avoid mutation issues
        }

        # Apply prediction if available
        if c_id in pred_map:
            pred = pred_map[c_id]
            
            # Update metadata directly with predicted values
            res_item["metadata"]["category"] = pred.category
            res_item["metadata"]["intent"] = pred.intent
            res_item["metadata"]["confidence_threshold"] = pred.confidence # Use confidence as threshold or score
            
            # Prepare update for Redis if requested
            if update_staging:
                updates_for_staging.append({
                    "chunk_id": c_id,
                    "metadata": {
                        "category": pred.category,
                        "intent": pred.intent,
                        "confidence_score": pred.confidence,
                        "extraction_method": "discovery" # Mark as discovered
                    }
                })
        
        results.append(res_item)
    
    # 4. Update Staging (if requested)
    if update_staging and updates_for_staging:
        await staging_service.update_chunk_metadata_batch(draft_id, updates_for_staging)
        
    return Envelope(
        data=results,
        meta=MetaResponse(trace_id=trace_id)
    )

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
