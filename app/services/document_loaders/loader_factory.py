"""Factory for creating appropriate document loader based on file type."""

import logging
from pathlib import Path

from .base_loader import BaseDocumentLoader
from .csv_loader import CSVLoader
from .docx_loader import DOCXLoader
from .md_loader import MarkdownLoader
from .pdf_loader import PDFLoader
from .models import DocumentFormat

logger = logging.getLogger(__name__)


class LoaderFactory:
    """Factory for creating document loaders."""

    _loaders = {
        DocumentFormat.PDF: PDFLoader,
        DocumentFormat.DOCX: DOCXLoader,
        DocumentFormat.CSV: CSVLoader,
        DocumentFormat.MARKDOWN: MarkdownLoader,
    }

    @staticmethod
    def detect_format(file_path: str) -> DocumentFormat:
        """Detect document format from file extension.

        Args:
            file_path: Path to document file

        Returns:
            DocumentFormat enum value

        Raises:
            ValueError: If format is not supported
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        format_map = {
            ".pdf": DocumentFormat.PDF,
            ".docx": DocumentFormat.DOCX,
            ".csv": DocumentFormat.CSV,
            ".md": DocumentFormat.MARKDOWN,
        }

        if extension not in format_map:
            raise ValueError(
                f"Unsupported file format: {extension}. "
                f"Supported: {', '.join(format_map.keys())}"
            )

        return format_map[extension]

    @classmethod
    def get_loader(cls, file_path: str, max_file_size_mb: int = 50) -> BaseDocumentLoader:
        """Get appropriate loader for a file.

        Args:
            file_path: Path to document file
            max_file_size_mb: Maximum file size in MB

        Returns:
            Instance of appropriate loader

        Raises:
            ValueError: If format is not supported
        """
        doc_format = cls.detect_format(file_path)
        loader_class = cls._loaders.get(doc_format)

        if not loader_class:
            raise ValueError(f"No loader available for format: {doc_format}")

        logger.debug(f"Using {loader_class.__name__} for {Path(file_path).name}")
        return loader_class(max_file_size_mb=max_file_size_mb)
