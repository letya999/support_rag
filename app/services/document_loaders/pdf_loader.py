"""PDF document loader using pdfplumber."""

import logging
from typing import List

import pdfplumber

from .base_loader import BaseDocumentLoader
from .models import DocumentContent, DocumentFormat, Block, BlockType

logger = logging.getLogger(__name__)


class PDFLoader(BaseDocumentLoader):
    """Loader for PDF documents."""

    def load(self, file_path: str) -> DocumentContent:
        """Load PDF and extract blocks (tables, text, lists).

        Args:
            file_path: Path to PDF file

        Returns:
            DocumentContent with extracted blocks
        """
        path = self._validate_file(file_path, ".pdf", self.max_file_size_mb)

        logger.info(f"Loading PDF: {path.name}")

        doc = DocumentContent(
            file_name=path.name,
            file_type=DocumentFormat.PDF,
            blocks=[],
            raw_text=""
        )

        try:
            with pdfplumber.open(path) as pdf:
                raw_text_parts = []

                for page_idx, page in enumerate(pdf.pages):
                    logger.debug(f"Processing PDF page {page_idx + 1}/{len(pdf.pages)}")

                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        for table_idx, table in enumerate(tables):
                            if table and len(table) > 0:
                                # Normalize table (ensure all rows have same number of columns)
                                max_cols = max(len(row) for row in table)
                                normalized_table = [
                                    row + [None] * (max_cols - len(row)) for row in table
                                ]

                                block = Block(
                                    type=BlockType.TABLE,
                                    content=normalized_table,
                                    metadata={
                                        "page": page_idx + 1,
                                        "table_index": table_idx
                                    },
                                    original_index=len(doc.blocks)
                                )
                                doc.blocks.append(block)

                    # Extract text
                    text = page.extract_text()
                    if text and text.strip():
                        raw_text_parts.append(text)

                        # Split text into paragraphs/sections as blocks
                        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

                        for para_idx, para in enumerate(paragraphs):
                            if para:
                                block = Block(
                                    type=BlockType.TEXT,
                                    content=para,
                                    metadata={
                                        "page": page_idx + 1,
                                        "paragraph_index": para_idx
                                    },
                                    original_index=len(doc.blocks)
                                )
                                doc.blocks.append(block)

                doc.raw_text = "\n\n".join(raw_text_parts)
                logger.info(
                    f"Extracted {len(doc.blocks)} blocks from PDF "
                    f"({len(pdf.pages)} pages, {len(doc.raw_text)} chars)"
                )

        except Exception as e:
            logger.error(f"Error loading PDF: {e}")
            raise ValueError(f"Failed to parse PDF file: {str(e)}")

        return doc
