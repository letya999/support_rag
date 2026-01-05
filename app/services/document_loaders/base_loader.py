"""Base loader interface for all document types."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import logging

from .models import DocumentContent, DocumentFormat

logger = logging.getLogger(__name__)


class BaseDocumentLoader(ABC):
    """Abstract base class for document loaders."""

    def __init__(self, max_file_size_mb: int = 50):
        """Initialize loader.

        Args:
            max_file_size_mb: Maximum file size in MB
        """
        self.max_file_size_mb = max_file_size_mb

    @abstractmethod
    def load(self, file_path: str) -> DocumentContent:
        """Load document and extract blocks.

        Args:
            file_path: Path to the document file

        Returns:
            DocumentContent with extracted blocks

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid or file is too large
        """
        pass

    @staticmethod
    def _validate_file(file_path: str, expected_extension: str, max_size_mb: int = 50) -> Path:
        """Validate file exists, has correct extension, and is not too large.

        Args:
            file_path: Path to check
            expected_extension: Expected file extension (e.g., '.pdf', '.docx')
            max_size_mb: Max file size in MB

        Returns:
            Path object if valid

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If extension or size is invalid
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if path.suffix.lower() != expected_extension.lower():
            raise ValueError(f"Expected {expected_extension} file, got {path.suffix}")

        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise ValueError(
                f"File size ({file_size_mb:.1f}MB) exceeds limit ({max_size_mb}MB)"
            )

        return path
