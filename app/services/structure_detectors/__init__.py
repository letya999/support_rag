"""Document structure detection for identifying Q&A formats."""

from .document_structure_analyzer import DocumentStructureAnalyzer
from .pattern_matcher import PatternMatcher

__all__ = [
    "DocumentStructureAnalyzer",
    "PatternMatcher",
]
