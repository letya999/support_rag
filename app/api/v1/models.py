from typing import Generic, TypeVar, Optional, List, Any, Dict
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")

class PaginationMeta(BaseModel):
    limit: int
    offset: int
    total: int

class MetaResponse(BaseModel):
    trace_id: str
    pagination: Optional[PaginationMeta] = None
    # Allow arbitrary extra fields in meta if needed, strictly typed though
    # For now we keep it simple as per spec, but extra dict can be useful
    extra: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class Envelope(BaseModel, Generic[DataT]):
    data: DataT
    meta: MetaResponse

class ErrorDetails(BaseModel):
    field: Optional[str] = None
    reason: str

class ErrorResponseModel(BaseModel):
    code: str
    message: str
    details: Optional[List[ErrorDetails]] = None
    trace_id: str

class ErrorEnvelope(BaseModel):
    error: ErrorResponseModel
