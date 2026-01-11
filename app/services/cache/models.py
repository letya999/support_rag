"""
Pydantic models for cache entries and statistics.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class CacheEntry(BaseModel):
    """
    Represents a cached FAQ entry.

    Example:
        CacheEntry(
            query_normalized="reset password",
            query_original="How to reset password?",
            answer="Click on 'Forgot Password' button...",
            doc_ids=["doc_1", "doc_2"],
            confidence=0.95,
            timestamp=datetime.now(),
            hit_count=5,
            user_rating=4.5
        )
    """
    query_normalized: str = Field(..., description="Normalized query for cache key")
    query_original: str = Field(..., description="Original question from user")
    answer: str = Field(..., description="Generated answer")
    doc_ids: List[str] = Field(default_factory=list, description="Source document IDs")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When entry was cached")
    hit_count: int = Field(default=0, ge=0, description="How many times this cache was used")
    user_rating: Optional[float] = Field(default=None, ge=1.0, le=5.0, description="User satisfaction rating")

    class Config:
        json_schema_extra = {
            "example": {
                "query_normalized": "reset password",
                "query_original": "How to reset password?",
                "answer": "To reset your password, click on 'Forgot Password'...",
                "doc_ids": ["faq_001", "faq_002"],
                "confidence": 0.95,
                "timestamp": "2024-01-03T12:30:00",
                "hit_count": 5,
                "user_rating": 4.5
            }
        }


class CacheStats(BaseModel):
    """
    Cache performance statistics.

    Tracks:
    - Hit/miss rates
    - Response time improvements
    - Memory usage
    - Most frequently asked questions
    """
    total_requests: int = Field(default=0, description="Total cache lookups")
    cache_hits: int = Field(default=0, description="Number of cache hits")
    cache_misses: int = Field(default=0, description="Number of cache misses")
    hit_rate: float = Field(default=0.0, description="Hit rate percentage (0-100)")
    avg_response_time_cached: float = Field(default=0.0, description="Average cached response time (ms)")
    avg_response_time_full: float = Field(default=0.0, description="Average full pipeline time (ms)")
    savings_time: float = Field(default=0.0, description="Total time saved by caching (seconds)")
    memory_usage_mb: float = Field(default=0.0, description="Cache memory usage (MB)")
    total_entries: int = Field(default=0, description="Number of cached entries")
    most_asked_questions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top 5 most frequently asked questions with hit counts"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_requests": 100,
                "cache_hits": 45,
                "cache_misses": 55,
                "hit_rate": 45.0,
                "avg_response_time_cached": 5.2,
                "avg_response_time_full": 850.0,
                "savings_time": 37.5,
                "memory_usage_mb": 2.5,
                "total_entries": 12,
                "most_asked_questions": [
                    {"query": "reset password", "hits": 15},
                    {"query": "check order status", "hits": 12}
                ]
            }
        }


class UserSession(BaseModel):
    """
    Represents an active user session in Redis.
    """
    user_id: str
    session_id: str
    start_time: float
    last_activity_time: float
    
    # Context
    current_problem: Optional[str] = None
    dialog_state: str = "INITIAL"
    attempt_count: int = 0
    
    # State tracking
    last_answer_confidence: Optional[float] = None
    last_emotion_detected: Optional[str] = None
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    
    # Clarification Flow Persistence
    clarification_context: Optional[Dict] = None  # Stores the ClarificationContext dict
    clarified_doc_ids: List[str] = Field(default_factory=list)
    
    # History (transient)
    message_count: int = 0
    recent_messages: List[Dict[str, str]] = Field(default_factory=list, description="List of recent messages (role, content)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "session_id": "sess_abc",
                "start_time": 1704280000.0,
                "last_activity_time": 1704280100.0,
                "current_problem": "login issue",
                "dialog_state": "AWAITING_CLARIFICATION",
                "attempt_count": 1,
                "last_answer_confidence": 0.4,
                "extracted_entities": {"device": "iphone"},
                "message_count": 3
            }
        }
