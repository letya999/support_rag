"""Q&A extractor for Markdown format documents."""

import logging

from app.services.document_loaders import Block, BlockType, DocumentStructure, RawQAPair

from .section_extractor import SectionQAExtractor

logger = logging.getLogger(__name__)


class MarkdownQAExtractor(SectionQAExtractor):
    """Extracts Q&A pairs from Markdown documents.

    Inherits from SectionQAExtractor since Markdown uses heading-based structure.
    """

    def extract(self, blocks: list, structure: DocumentStructure) -> list:
        """Extract Q&A pairs from Markdown format.

        Markdown structure is similar to sections with headings.

        Args:
            blocks: List of document blocks
            structure: Document structure

        Returns:
            List of extracted Q&A pairs
        """
        logger.info("Using Markdown extraction (section-based)")
        # Use parent's section extraction which works well for Markdown
        return super().extract(blocks, structure)
