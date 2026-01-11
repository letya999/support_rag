from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import shutil
import tempfile
import os
import json

from app.api.v1.models import Envelope, MetaResponse
from app.services.staging import staging_service

router = APIRouter(tags=["Knowledge Base"])

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

class ManualChunksRequest(BaseModel):
    draft_id: Optional[str] = None # If None, creates new draft
    chunks: List[ChunkCreate]

class ManualChunksUpdate(BaseModel):
    draft_id: str
    updates: List[ChunkUpdate]
    
class CommitRequest(BaseModel):
    draft_id: str
    action: str = Field("commit", pattern="^commit$")

class KnowledgeResponse(BaseModel):
    file_id: Optional[str] = None
    draft_id: str
    extracted_pairs: Optional[List[Dict[str, Any]]] = None
    total_pairs: int

class ContractResponse(BaseModel):
    supported_formats: List[str]
    max_pairs: int
    max_question_length: int
    max_answer_length: int
    json_schema: List[Any]

# Endpoints

@router.get("/knowledge/contract", response_model=Envelope[ContractResponse])
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

from app.services.document_processing import DocumentProcessingService

# ... imports ...

@router.post("/knowledge/upload", response_model=Envelope[KnowledgeResponse])
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    Upload file -> Staging.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    # Save to temp file
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
        
    try:
        # Process file using valid pipeline (Loader -> Analyzer -> Extractor)
        pairs = await DocumentProcessingService.process_file(tmp_path)
        
        # Convert ProcessedQAPair objects to dicts for staging
        pairs_dicts = [
            {"question": p.question, "answer": p.answer, "metadata": p.metadata} 
            for p in pairs
        ]
        
        draft = await staging_service.create_draft(file.filename, pairs_dicts)
        
        return Envelope(
            data=KnowledgeResponse(
                file_id=draft["file_id"],
                draft_id=draft["draft_id"],
                extracted_pairs=draft["chunks"],
                total_pairs=len(pairs)
            ),
            meta=MetaResponse(trace_id=trace_id)
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@router.post("/knowledge/chunks", response_model=Envelope[KnowledgeResponse])
async def add_chunks(request: Request, body: ManualChunksRequest):
    """
    Add manual chunks to staging.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    chunks_data = [c.model_dump() for c in body.chunks]
    
    try:
        if body.draft_id:
            draft = await staging_service.add_chunks(body.draft_id, chunks_data)
            if not draft:
                raise HTTPException(status_code=404, detail="Draft not found")
        else:
            draft = await staging_service.create_draft("manual_upload.json", chunks_data)
            
        return Envelope(
            data=KnowledgeResponse(
                file_id=draft["file_id"],
                draft_id=draft["draft_id"],
                extracted_pairs=draft["chunks"],
                total_pairs=len(draft["chunks"])
            ),
            meta=MetaResponse(trace_id=trace_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/knowledge/chunks", response_model=Envelope[KnowledgeResponse])
async def update_chunks(request: Request, body: ManualChunksUpdate):
    """
    Update chunks in staging.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    try:
        # Handling multiple updates
        # StagingService.update_chunk updates one at a time.
        # We'll loop.
        current_draft = None
        for update in body.updates:
            updates_dict = update.model_dump(exclude_unset=True, exclude={"chunk_id"})
            current_draft = await staging_service.update_chunk(body.draft_id, update.chunk_id, updates_dict)
            
        if not current_draft:
             # Try get it just in case no updates were valid or draft not found
             current_draft = await staging_service.get_draft(body.draft_id)
             if not current_draft:
                 raise HTTPException(status_code=404, detail="Draft not found")

        return Envelope(
            data=KnowledgeResponse(
                file_id=current_draft["file_id"],
                draft_id=current_draft["draft_id"],
                extracted_pairs=current_draft["chunks"],
                total_pairs=len(current_draft["chunks"])
            ),
            meta=MetaResponse(trace_id=trace_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/knowledge/chunks/{chunk_id}", response_model=Envelope[Dict[str, str]])
async def delete_chunk(request: Request, chunk_id: str, draft_id: str):
    """
    Delete chunk from staging.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    success = await staging_service.delete_chunk(draft_id, chunk_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chunk or Draft not found")
        
    return Envelope(
        data={"status": "deleted", "chunk_id": chunk_id},
        meta=MetaResponse(trace_id=trace_id)
    )

@router.delete("/knowledge/files/{file_id}", response_model=Envelope[Dict[str, str]])
async def delete_file(request: Request, file_id: str):
    """
    Delete file and staging data.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    draft = await staging_service.get_draft_by_file(file_id)
    if draft:
        await staging_service.delete_draft(draft["draft_id"])
        
    # We return success even if not found (idempotent-ish) or 404? 
    # Plan says "Delete file and staging data".
    return Envelope(
        data={"status": "deleted", "file_id": file_id},
        meta=MetaResponse(trace_id=trace_id)
    )

@router.post("/knowledge/commit", response_model=Envelope[Dict[str, Any]])
async def commit_staging(request: Request, body: CommitRequest):
    """
    Commit staging to Prod.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    try:
        result = await staging_service.commit_draft(body.draft_id)
        return Envelope(
            data=result,
            meta=MetaResponse(trace_id=trace_id)
        )
    except ValueError as e:
         raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))
