"""
Pydantic models for metadata generation service.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class MetadataConfig(BaseModel):
    """Configuration for metadata generation."""

    confidence_threshold_high: float = Field(
        default=0.75,
        description="Threshold above which we trust embedding classification"
    )
    confidence_threshold_low: float = Field(
        default=0.70,
        description="Threshold for intent validation"
    )
    context_examples_count: int = Field(
        default=3,
        description="Number of example questions to retrieve for context"
    )
    context_chunks_count: int = Field(
        default=3,
        description="Number of answer chunks to retrieve for context"
    )
    chunk_preview_length: int = Field(
        default=150,
        description="Characters to extract from answer chunks"
    )
    llm_batch_size: int = Field(
        default=20,
        description="Number of items per LLM batch"
    )
    max_parallel_batches: int = Field(
        default=5,
        description="Maximum parallel LLM batch requests"
    )


class ClassificationResult(BaseModel):
    """Result of embedding classification."""

    category: str
    confidence: float
    method: str = "embedding"  # "embedding" or "llm"
    needs_llm_validation: bool = Field(
        default=False,
        description="Whether LLM validation is needed"
    )


class ContextExample(BaseModel):
    """Example question/chunk from a category."""

    content: str
    metadata: Optional[Dict[str, Any]] = None


class CategoryContext(BaseModel):
    """Context information for a category."""

    category: str
    examples: List[ContextExample]


class LLMValidationRequest(BaseModel):
    """Request for LLM validation."""

    question: str
    predicted_category: str
    confidence: float
    context: CategoryContext


class LLMValidationResult(BaseModel):
    """Result of LLM validation."""

    is_correct: bool
    suggested_category: str
    confidence: float
    reasoning: Optional[str] = None


class HandoffResult(BaseModel):
    """Result of handoff detection."""

    requires_handoff: bool
    confidence_threshold: float
    clarifying_questions: List[str] = Field(default_factory=list)
    matched_pattern: Optional[str] = None


class QAPairMetadata(BaseModel):
    """Complete metadata for a Q&A pair."""

    category: str
    intent: str = "unknown"
    requires_handoff: bool = False
    confidence_threshold: float = 0.95
    clarifying_questions: List[str] = Field(default_factory=list)
    confidence_scores: Dict[str, Any] = Field(
        default_factory=lambda: {
            "category": 0.0,
            "intent": 0.0,
            "validation_method": "embedding"
        }
    )


class QAPairWithMetadata(BaseModel):
    """Q&A pair with generated metadata."""

    qa_index: int
    question: str
    answer: str
    metadata: QAPairMetadata


class AnalysisResult(BaseModel):
    """Complete analysis result for batch of Q&A pairs."""

    analysis_id: str
    total_pairs: int
    high_confidence_count: int
    low_confidence_count: int
    llm_validated_count: int
    qa_with_metadata: List[QAPairWithMetadata]
    statistics: Dict[str, Any]


class AnalysisStats(BaseModel):
    """Statistics from analysis."""

    total_items: int
    embedding_classified: int
    llm_validated: int
    embedding_percentage: float
    llm_percentage: float
    avg_category_confidence: float
    avg_intent_confidence: float
    handoff_count: int
    processing_time_seconds: float
