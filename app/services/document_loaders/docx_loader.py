"""DOCX document loader using python-docx."""

import logging
from typing import List

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph

from .base_loader import BaseDocumentLoader
from .models import DocumentContent, DocumentFormat, Block, BlockType

logger = logging.getLogger(__name__)


class DOCXLoader(BaseDocumentLoader):
    """Loader for DOCX documents."""

    def load(self, file_path: str) -> DocumentContent:
        """Load DOCX and extract blocks (tables, paragraphs, lists).

        Args:
            file_path: Path to DOCX file

        Returns:
            DocumentContent with extracted blocks
        """
        path = self._validate_file(file_path, ".docx", self.max_file_size_mb)

        logger.info(f"Loading DOCX: {path.name}")

        doc = DocumentContent(
            file_name=path.name,
            file_type=DocumentFormat.DOCX,
            blocks=[],
            raw_text=""
        )

        try:
            docx_doc = Document(path)
            raw_text_parts = []

            # Iterate through document body elements while preserving order
            for element in docx_doc.element.body:
                if isinstance(element, CT_Tbl):
                    # This is a table
                    table = Table(element, docx_doc)
                    table_data = self._extract_table(table)

                    if table_data and len(table_data) > 0:
                        block = Block(
                            type=BlockType.TABLE,
                            content=table_data,
                            metadata={"type": "docx_table"},
                            original_index=len(doc.blocks)
                        )
                        doc.blocks.append(block)

                else:
                    # This is a paragraph
                    para = Paragraph(element, docx_doc)
                    text = (para.text or "").strip()

                    if text:
                        raw_text_parts.append(text)

                        # Safely get style name
                        style_name = "Normal"
                        if para.style and hasattr(para.style, "name"):
                            style_name = para.style.name

                        # Determine block type based on style
                        block_type = BlockType.HEADING if style_name.startswith("Heading") else BlockType.TEXT

                        block = Block(
                            type=block_type,
                            content=text,
                            metadata={
                                "style": style_name,
                                "level": self._get_heading_level(style_name)
                            },
                            original_index=len(doc.blocks)
                        )
                        doc.blocks.append(block)

            doc.raw_text = "\n\n".join(raw_text_parts)
            logger.info(
                f"Extracted {len(doc.blocks)} blocks from DOCX "
                f"({len(doc.raw_text)} chars)"
            )

        except Exception as e:
            logger.error(f"Error loading DOCX: {e}")
            raise ValueError(f"Failed to parse DOCX file: {str(e)}")

        return doc

    @staticmethod
    def _extract_table(table: Table) -> List[List[str]]:
        """Extract data from a table.

        Args:
            table: python-docx Table object

        Returns:
            2D list of cell contents
        """
        table_data = []
        for row in table.rows:
            row_data = []
            for cell in row.cells:
                # Get text from all paragraphs in the cell
                cell_text = "\n".join((p.text or "") for p in cell.paragraphs).strip()
                row_data.append(cell_text)
            if row_data:
                table_data.append(row_data)
        return table_data

    @staticmethod
    def _get_heading_level(style_name: str) -> int:
        """Extract heading level from style name.

        Args:
            style_name: Style name like "Heading 1"

        Returns:
            Heading level (1-6) or 0 if not a heading
        """
        if not style_name.startswith("Heading"):
            return 0

        parts = style_name.split()
        if len(parts) > 1 and parts[1].isdigit():
            return int(parts[1])
        return 1
