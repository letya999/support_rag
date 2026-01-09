"""
Metadata Generation Service

CPU-first automatic Q&A metadata generation:
- Sentence-transformers for embeddings
- Sklearn clustering for category discovery  
- TF-IDF + patterns for category/intent naming
- LLM validation ONLY for low-confidence cases (minimal API calls)
"""

from .auto_classifier import AutoClassificationPipeline, ClassificationResult, CategoryInfo
from .handoff_detector import HandoffDetector
from .metadata_analyzer import MetadataAnalyzerService

__all__ = [
    "AutoClassificationPipeline",
    "ClassificationResult", 
    "CategoryInfo",
    "HandoffDetector",
    "MetadataAnalyzerService",
]
