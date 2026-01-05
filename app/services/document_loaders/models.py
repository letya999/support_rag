"""Data models for document loading and processing."""

from typing import List, Union, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class BlockType(str, Enum):
    """Types of content blocks in documents."""
    TABLE = "table"
    TEXT = "text"
    LIST = "list"
    HEADING = "heading"
    IMAGE = "image"


class DocumentFormat(str, Enum):
    """Supported document formats."""
    PDF = "pdf"
    DOCX = "docx"
    CSV = "csv"
    MARKDOWN = "md"


@dataclass
class Block:
    """Represents a content block extracted from a document."""

    type: BlockType
    content: Union[str, List[List[str]]]  # str for text, List[List[str]] for tables
    metadata: Dict[str, Any] = field(default_factory=dict)
    original_index: int = 0

    def __repr__(self) -> str:
        content_preview = str(self.content)[:100] if isinstance(self.content, str) else f"Table({len(self.content)}x{len(self.content[0]) if self.content else 0})"
        return f"Block(type={self.type}, content='{content_preview}...', index={self.original_index})"


@dataclass
class DocumentContent:
    """Represents a loaded document with all its blocks."""

    file_name: str
    file_type: DocumentFormat
    blocks: List[Block] = field(default_factory=list)
    raw_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.blocks)


class RawQAPair:
    """Represents an extracted Q&A pair before validation."""

    def __init__(
        self,
        question: str,
        answer: str,
        source_block_ids: List[int],
        extraction_method: str,
        confidence: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.question = question
        self.answer = answer
        self.source_block_ids = source_block_ids
        self.extraction_method = extraction_method
        self.confidence = confidence
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        q_preview = self.question[:50]
        return f"RawQAPair(q='{q_preview}...', confidence={self.confidence:.2f}, method={self.extraction_method})"


class ProcessedQAPair:
    """Represents a validated and processed Q&A pair ready for ingestion."""

    def __init__(
        self,
        question: str,
        answer: str,
        metadata: Optional[Dict[str, Any]] = None,
        confidence_score: float = 0.0,
        extraction_method: str = ""
    ):
        self.question = question
        self.answer = answer
        self.metadata = metadata or {
            "category": "General",
            "intent": "provide_info",
            "requires_handoff": False,
            "confidence_threshold": 0.8,
            "clarifying_questions": [],
            "source_document": "",
            "extraction_date": "",
            "extraction_method": extraction_method,
            "confidence_score": confidence_score
        }
        self.confidence_score = confidence_score

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "question": self.question,
            "answer": self.answer,
            "metadata": self.metadata
        }

    def __repr__(self) -> str:
        q_preview = self.question[:50]
        return f"ProcessedQAPair(q='{q_preview}...', category={self.metadata.get('category')})"


@dataclass
class ValidationResult:
    """Result of validating a Q&A pair."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def __repr__(self) -> str:
        status = "✓ VALID" if self.is_valid else "✗ INVALID"
        return f"ValidationResult({status}, confidence={self.confidence:.2f}, errors={len(self.errors)}, warnings={len(self.warnings)})"


@dataclass
class DocumentStructure:
    """Analysis result of document structure."""

    detected_format: str  # "table", "list", "faq", "sections", "two_column", "unknown"
    confidence: float  # 0.0-1.0
    column_mapping: Dict[int, str] = field(default_factory=dict)  # For tables
    block_assignments: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"DocumentStructure(format={self.detected_format}, confidence={self.confidence:.2f}, notes={len(self.notes)})"


@dataclass
class FileError:
    """Represents an error processing a file."""

    file_name: str
    error_type: str  # "file_not_found", "unsupported_format", "parsing_error", "validation_error"
    error_message: str
    line_number: Optional[int] = None
    traceback: Optional[str] = None


@dataclass
class BatchResult:
    """Final result of batch processing."""

    total_files: int
    processed_files: int
    failed_files: List[FileError] = field(default_factory=list)
    qa_pairs: List[ProcessedQAPair] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    processing_time_sec: float = 0.0

    @property
    def summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        return {
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "failed_files": len(self.failed_files),
            "total_pairs_found": len(self.qa_pairs),
            "average_confidence": sum(p.confidence_score for p in self.qa_pairs) / len(self.qa_pairs) if self.qa_pairs else 0.0,
            "processing_time_sec": self.processing_time_sec
        }

    def __repr__(self) -> str:
        return f"BatchResult(processed={self.processed_files}/{self.total_files}, pairs={len(self.qa_pairs)}, time={self.processing_time_sec:.2f}s)"
