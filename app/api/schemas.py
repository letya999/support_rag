from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    q: str
    top_k: int = 3


class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    docs: List[str]
    metadata: Dict[str, Any]


# Document upload schemas
class QAPairResponse(BaseModel):
    """Response containing a single Q&A pair."""

    question: str
    answer: str
    metadata: Dict[str, Any]


class DocumentUploadResponse(BaseModel):
    """Response from document upload endpoint."""

    total_files: int
    processed_files: int
    failed_files: List[Dict[str, Any]]
    qa_pairs: List[QAPairResponse]
    warnings: List[str]
    summary: Dict[str, Any]


class DocumentConfirmRequest(BaseModel):
    """Request to confirm upload and ingest Q&A pairs."""

    qa_pairs: List[QAPairResponse]
    batch_id: Optional[str] = None


class DocumentConfirmResponse(BaseModel):
    """Response from document confirm endpoint."""

    status: str
    ingested_count: int
    message: Optional[str] = None
