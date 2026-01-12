from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

# --- Webhook Management Schemas ---

class WebhookCreate(BaseModel):
    name: str
    description: Optional[str] = None
    url: HttpUrl
    events: List[str]
    secret: Optional[str] = None # Optional, if not provided can be auto-generated
    active: bool = True
    metadata: Optional[Dict[str, Any]] = None
    ip_whitelist: Optional[List[str]] = None

class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[HttpUrl] = None
    events: Optional[List[str]] = None
    active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    ip_whitelist: Optional[List[str]] = None

class WebhookResponse(BaseModel):
    webhook_id: str
    name: str
    description: Optional[str]
    url: str
    events: List[str]
    active: bool
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]]
    # Don't return secret in list/get unless explicitly requested or mainly on creation
    
class WebhookResponseFull(WebhookResponse):
    secret_hash: str # Or maybe a masked version? The plan says "secret_hash" in DB. 
    # Usually we show the secret only once upon creation.

class WebhookSecretResponse(BaseModel):
    webhook_id: str
    secret: str # Clear text secret, only shown once

# --- Delivery History Schemas ---

class WebhookDeliveryResponse(BaseModel):
    delivery_id: str
    webhook_id: str
    event_id: str
    event_type: str
    status: str
    http_status: Optional[int]
    attempt: int
    next_retry: Optional[datetime]
    response_time_ms: Optional[int]
    created_at: datetime
    error_message: Optional[str]

# --- Incoming Webhook Schemas ---

class IncomingWebhookRequest(BaseModel):
    event_type: str
    timestamp: datetime
    source: str
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

class IncomingWebhookResponse(BaseModel):
    webhook_event_id: str
    status: str
    session_id: Optional[str] = None
    message: str

# --- Outgoing Webhook Payloads ---
# Defining these allows us to auto-generate AsyncAPI or documentation

class ChatResponseGeneratedPayload(BaseModel):
    session_id: str
    user_id: str
    answer: str
    confidence: float
    query_id: str

class ChatEscalatedPayload(BaseModel):
    session_id: str
    reason: str
    user_id: Optional[str] = None

class DocumentUploadedPayload(BaseModel):
    document_name: str
    staging_id: str
    total_pairs: int

class DocumentIndexedPayload(BaseModel):
    draft_id: str
    result: Dict[str, Any]

class DocumentFailedPayload(BaseModel):
    error: str
    filename: str

class ClassificationCompletedPayload(BaseModel):
    document_id: str
    classifications_count: int
    method: str

