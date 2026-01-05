"""Factory for creating appropriate QA extractor based on document structure."""

import logging

from app.services.document_loaders import DocumentStructure

from .base_extractor import BaseQAExtractor
from .faq_extractor import FAQExtractor
from .list_extractor import ListQAExtractor
from .markdown_extractor import MarkdownQAExtractor
from .section_extractor import SectionQAExtractor
from .table_extractor import TableQAExtractor
from .two_column_extractor import TwoColumnExtractor

logger = logging.getLogger(__name__)


class ExtractorFactory:
    """Factory for creating appropriate QA extractors."""

    _extractors = {
        "table": TableQAExtractor,
        "faq": FAQExtractor,
        "list": ListQAExtractor,
        "sections": SectionQAExtractor,
        "markdown": MarkdownQAExtractor,
        "two_column": TwoColumnExtractor,
    }

    @classmethod
    def get_extractor(cls, structure: DocumentStructure) -> BaseQAExtractor:
        """Get appropriate extractor based on detected structure.

        Args:
            structure: Analyzed document structure

        Returns:
            Instance of appropriate extractor

        Raises:
            ValueError: If format is not supported
        """
        format_name = structure.detected_format.lower()

        extractor_class = cls._extractors.get(format_name, ListQAExtractor)

        logger.debug(f"Using {extractor_class.__name__} for format: {format_name}")
        return extractor_class()

    @classmethod
    def get_available_formats(cls) -> list:
        """Get list of supported formats.

        Returns:
            List of supported format names
        """
        return list(cls._extractors.keys())
