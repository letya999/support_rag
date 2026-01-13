from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Query, Body, Path, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import shutil
import tempfile
import os
import json

from app.api.v1.models import Envelope, MetaResponse
from app.services.staging import staging_service
from app.services.document_processing import DocumentProcessingService
from app.services.webhook_service import WebhookService
from app.utils.file_security import validate_file_type, sanitize_filename
from app.api.v1.limiter import strict_limiter

router = APIRouter(tags=["Ingestion"])

# Models
class ChunkMetadata(BaseModel):
    source: Optional[str] = None
    category: Optional[str] = None
    intent: Optional[str] = None
    
class ChunkCreate(BaseModel):
    question: str
    answer: str
    metadata: Optional[Dict[str, Any]] = None

class ChunkUpdate(BaseModel):
    chunk_id: str
    question: Optional[str] = None
    answer: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ManualDraftCreate(BaseModel):
    filename: str = "manual_draft.json"
    chunks: List[ChunkCreate]

class ManualChunksAdd(BaseModel):
    chunks: List[ChunkCreate]

class ChunkUpdateBatch(BaseModel):
    updates: List[ChunkUpdate]
    
class CommitRequest(BaseModel):
    draft_id: str
    action: str = Field("commit", pattern="^commit$")

class KnowledgeResponse(BaseModel):
    file_id: Optional[str] = None
    draft_id: str
    filename: Optional[str] = None
    extracted_pairs: Optional[List[Dict[str, Any]]] = None
    total_pairs: int

class ContractResponse(BaseModel):
    supported_formats: List[str]
    max_pairs: int
    max_question_length: int
    max_answer_length: int
    json_schema: List[Any]

# Endpoints

@router.get("/ingestion/contract", response_model=Envelope[ContractResponse])
async def get_contract(request: Request):
    """
    Get API contract / supported formats.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    # Schema definition
    schema_def = {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "question": {"type": "string"},
            "answer": {"type": "string"},
            "metadata": {
              "type": "object",
              "properties": {
                "category": {"type": "string"},
                "intent": {"type": "string"},
                "requires_handoff": {"type": "boolean"},
                "confidence_threshold": {"type": "number"},
                "clarifying_questions": {
                  "type": "array",
                  "items": {"type": "string"}
                }
              }
            }
          },
          "required": ["question", "answer"]
        }
    }
    
    # Helper example
    example_item = {
        "question": "How do I reset my password?",
        "answer": "You can reset your password by clicking on the 'Forgot Password' link on the login page.",
        "metadata": {
            "category": "Account Access",
            "intent": "reset_password",
            "requires_handoff": False,
            "confidence_threshold": 0.9,
            "clarifying_questions": [
                "Do you have access to the email address associated with your account?"
            ]
        }
    }
    
    return Envelope(
        data=ContractResponse(
            supported_formats=["json", "pdf", "csv", "md", "docx"],
            max_pairs=100,
            max_question_length=500,
            max_answer_length=5000,
            json_schema=[schema_def, example_item]
        ),
        meta=MetaResponse(trace_id=trace_id)
    )

@router.post("/ingestion/upload", response_model=Envelope[KnowledgeResponse], dependencies=[Depends(strict_limiter)])
async def upload_file(request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Upload file -> Staging.
    Creates a new draft from the file.
    """
    trace_id = getattr(request.state, "trace_id", None)

    # Sanitize filename
    try:
        safe_filename = sanitize_filename(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid filename: {str(e)}")

    # Save to temp file
    suffix = os.path.splitext(safe_filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    # Validate file type using magic bytes
    try:
        extension, mime_type = validate_file_type(tmp_path, safe_filename)
    except ValueError as e:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail=f"File validation failed: {str(e)}")

    try:
        # Process file using valid pipeline (Loader -> Analyzer -> Extractor)
        pairs = await DocumentProcessingService.process_file(tmp_path, original_filename=safe_filename)

        # Convert ProcessedQAPair objects to dicts for staging
        pairs_dicts = [
            {"question": p.question, "answer": p.answer, "metadata": p.metadata}
            for p in pairs
        ]

        draft = await staging_service.create_draft(safe_filename, pairs_dicts)
        
        # Trigger Webhook
        background_tasks.add_task(
            WebhookService.trigger_outgoing_event,
            event_type="knowledge.document.uploaded",
            payload={
                "document_name": safe_filename,
                "staging_id": draft["draft_id"],
                "total_pairs": len(pairs)
            }
        )

        return Envelope(
            data=KnowledgeResponse(
                file_id=draft["file_id"],
                draft_id=draft["draft_id"],
                filename=draft.get("filename"),
                extracted_pairs=draft["chunks"],
                total_pairs=len(pairs)
            ),
            meta=MetaResponse(trace_id=trace_id)
        )
        
    except ValueError as e:
        background_tasks.add_task(
            WebhookService.trigger_outgoing_event,
            event_type="knowledge.document.failed",
            payload={"error": "File processing failed", "filename": safe_filename}
        )
        raise HTTPException(status_code=400, detail="File processing failed")
    except Exception as e:
        background_tasks.add_task(
            WebhookService.trigger_outgoing_event,
            event_type="knowledge.document.failed",
            payload={"error": "Internal error", "filename": safe_filename}
        )
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@router.delete("/ingestion/staging_draft/all", response_model=Envelope[Dict[str, Any]])
async def clear_all_drafts(request: Request):
    """
    Delete ALL staging drafts.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    count = await staging_service.clear_all_drafts()
    
    return Envelope(
        data={"status": "cleared", "deleted_count": count},
        meta=MetaResponse(trace_id=trace_id)
    )

# --- Staging Draft CRUDL ---

@router.get("/ingestion/staging_draft", response_model=Envelope[List[KnowledgeResponse]])
async def list_drafts(
    request: Request, 
    draft_ids: Optional[List[str]] = Query(None), 
    search: Optional[str] = Query(None)
):
    """
    List staging drafts.
    Optional filtering by draft_ids and search term (filename).
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    drafts = await staging_service.list_drafts(draft_ids=draft_ids, search_term=search)
    
    response_data = []
    for d in drafts:
        response_data.append(KnowledgeResponse(
            file_id=d.get("file_id"),
            draft_id=d.get("draft_id"),
            filename=d.get("filename"),
            extracted_pairs=d.get("chunks"),
            total_pairs=len(d.get("chunks", []))
        ))
        
    return Envelope(
        data=response_data,
        meta=MetaResponse(trace_id=trace_id)
    )

@router.post("/ingestion/staging_draft", response_model=Envelope[KnowledgeResponse])
async def create_draft(request: Request, body: ManualDraftCreate):
    """
    Create a new manual draft.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    chunks_data = [c.model_dump() for c in body.chunks]
    
    try:
        draft = await staging_service.create_draft(body.filename, chunks_data)
        
        return Envelope(
            data=KnowledgeResponse(
                file_id=draft["file_id"],
                draft_id=draft["draft_id"],
                filename=draft.get("filename"),
                extracted_pairs=draft["chunks"],
                total_pairs=len(draft["chunks"])
            ),
            meta=MetaResponse(trace_id=trace_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ingestion/staging_draft/{draft_id}", response_model=Envelope[KnowledgeResponse])
async def get_draft(request: Request, draft_id: str):
    """
    Get a specific staging draft.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    draft = await staging_service.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
        
    return Envelope(
        data=KnowledgeResponse(
            file_id=draft.get("file_id"),
            draft_id=draft.get("draft_id"),
            filename=draft.get("filename"),
            extracted_pairs=draft.get("chunks"),
            total_pairs=len(draft.get("chunks", []))
        ),
        meta=MetaResponse(trace_id=trace_id)
    )

@router.delete("/ingestion/staging_draft/{draft_id}", response_model=Envelope[Dict[str, str]])
async def delete_draft(request: Request, draft_id: str):
    """
    Delete a staging draft.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    success = await staging_service.delete_draft(draft_id)
    if not success:
        raise HTTPException(status_code=404, detail="Draft not found") 
    
    return Envelope(
        data={"status": "deleted", "draft_id": draft_id},
        meta=MetaResponse(trace_id=trace_id)
    )

# --- Chunk Management ---

@router.post("/ingestion/staging_draft/{draft_id}/chunks", response_model=Envelope[KnowledgeResponse])
async def add_chunks_to_draft(request: Request, draft_id: str, body: ManualChunksAdd):
    """
    Add chunks to an existing draft.
    """
    trace_id = getattr(request.state, "trace_id", None)
    chunks_data = [c.model_dump() for c in body.chunks]
    
    try:
        draft = await staging_service.add_chunks(draft_id, chunks_data)
        if not draft:
             raise HTTPException(status_code=404, detail="Draft not found")
             
        return Envelope(
            data=KnowledgeResponse(
                file_id=draft["file_id"],
                draft_id=draft["draft_id"],
                filename=draft.get("filename"),
                extracted_pairs=draft["chunks"],
                total_pairs=len(draft["chunks"])
            ),
            meta=MetaResponse(trace_id=trace_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/ingestion/staging_draft/{draft_id}/chunks/{chunk_id}", response_model=Envelope[Dict[str, str]])
async def delete_chunk_from_draft(request: Request, draft_id: str, chunk_id: str):
    """
    Delete a chunk from a draft.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    success = await staging_service.delete_chunk(draft_id, chunk_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chunk or Draft not found")
        
    return Envelope(
        data={"status": "deleted", "chunk_id": chunk_id, "draft_id": draft_id},
        meta=MetaResponse(trace_id=trace_id)
    )

@router.patch("/ingestion/staging_draft/{draft_id}/chunks", response_model=Envelope[KnowledgeResponse])
async def update_chunks_in_draft(request: Request, draft_id: str, body: ChunkUpdateBatch):
    """
    Update multiple chunks in a draft.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    try:
        current_draft = None
        # Loop through updates as service updates one by one (or check if batch exists)
        # Service has update_chunk (single) and update_chunk_metadata_batch (batch metadata).
        # We need full update (question/answer too). StagingService.update_chunk does that.
        
        for update in body.updates:
            updates_dict = update.model_dump(exclude_unset=True, exclude={"chunk_id"})
            current_draft = await staging_service.update_chunk(draft_id, update.chunk_id, updates_dict)
            
        if not current_draft:
             # Try get it just in case no updates were valid or draft not found
             current_draft = await staging_service.get_draft(draft_id)
             if not current_draft:
                 raise HTTPException(status_code=404, detail="Draft not found")

        return Envelope(
            data=KnowledgeResponse(
                file_id=current_draft["file_id"],
                draft_id=current_draft["draft_id"],
                filename=current_draft.get("filename"),
                extracted_pairs=current_draft["chunks"],
                total_pairs=len(current_draft["chunks"])
            ),
            meta=MetaResponse(trace_id=trace_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Commit ---

@router.post("/ingestion/commit", response_model=Envelope[Dict[str, Any]])
async def commit_staging(request: Request, body: CommitRequest, background_tasks: BackgroundTasks):
    """
    Commit staging to Prod.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    try:
        result = await staging_service.commit_draft(body.draft_id)
        
        # Trigger Webhook
        background_tasks.add_task(
            WebhookService.trigger_outgoing_event, 
            event_type="knowledge.document.indexed",
            payload={
                "draft_id": body.draft_id,
                "result": result
            }
        )
        
        return Envelope(
            data=result,
            meta=MetaResponse(trace_id=trace_id)
        )
    except ValueError as e:
         raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))
