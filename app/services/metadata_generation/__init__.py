"""
Metadata Generation Service

Hybrid approach for automatic Q&A metadata generation:
- Fast embedding-based classification (no ML training required)
- LLM validation with context for low-confidence predictions
- Rule-based handoff detection
"""

from .analyzer import HybridMetadataAnalyzer
from .embedding_classifier import EmbeddingClassifier
from .context_retriever import ContextRetriever
from .llm_validator import LLMValidator
from .handoff_detector import HandoffDetector

__all__ = [
    "HybridMetadataAnalyzer",
    "EmbeddingClassifier",
    "ContextRetriever",
    "LLMValidator",
    "HandoffDetector",
]
