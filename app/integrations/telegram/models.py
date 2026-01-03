"""
Telegram Bot Models

Pydantic models for user sessions, messages, and RAG pipeline communication.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from enum import Enum


class MessageRole(str, Enum):
    """Role of the message sender"""
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """Single message in conversation history"""
    role: MessageRole
    content: str
    timestamp: datetime
    query_id: Optional[str] = None  # ID from RAG pipeline for tracking


class UserSession(BaseModel):
    """User session with conversation history"""
    user_id: int
    username: str
    messages: List[Message] = []
    created_at: datetime
    last_activity: datetime
    is_active: bool = True


class RAGRequest(BaseModel):
    """Request to RAG pipeline"""
    question: str
    conversation_history: List[dict]  # [{"role": "user", "content": "..."}, ...]
    user_id: str
    session_id: str


class RAGResponse(BaseModel):
    """Response from RAG pipeline"""
    answer: str
    sources: List[dict]  # [{"title": str, "doc_id": str, "relevance": float}, ...]
    confidence: float
    query_id: str
    metadata: Optional[dict] = None
