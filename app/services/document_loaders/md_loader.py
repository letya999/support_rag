"""Markdown document loader."""

import logging
import re
from pathlib import Path

from .base_loader import BaseDocumentLoader
from .models import DocumentContent, DocumentFormat, Block, BlockType

logger = logging.getLogger(__name__)


class MarkdownLoader(BaseDocumentLoader):
    """Loader for Markdown documents."""

    def load(self, file_path: str) -> DocumentContent:
        """Load Markdown and extract blocks (headings, paragraphs, code blocks, lists).

        Args:
            file_path: Path to Markdown file

        Returns:
            DocumentContent with extracted blocks
        """
        path = self._validate_file(file_path, ".md", self.max_file_size_mb)

        logger.info(f"Loading Markdown: {path.name}")

        doc = DocumentContent(
            file_name=path.name,
            file_type=DocumentFormat.MARKDOWN,
            blocks=[],
            raw_text=""
        )

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            doc.raw_text = content

            # Split by double newlines to get logical blocks
            logical_blocks = content.split("\n\n")

            for block_idx, block_content in enumerate(logical_blocks):
                if not block_content.strip():
                    continue

                block_type, block_text = self._classify_block(block_content.strip())

                block = Block(
                    type=block_type,
                    content=block_text,
                    metadata={
                        "type": "markdown",
                        "markdown_type": block_type.value
                    },
                    original_index=len(doc.blocks)
                )
                doc.blocks.append(block)

            logger.info(f"Extracted {len(doc.blocks)} blocks from Markdown ({len(content)} chars)")

        except Exception as e:
            logger.error(f"Error loading Markdown: {e}")
            raise ValueError(f"Failed to parse Markdown file: {str(e)}")

        return doc

    @staticmethod
    def _classify_block(block_content: str) -> tuple:
        """Classify a block of content and extract text.

        Args:
            block_content: Block content to classify

        Returns:
            Tuple of (BlockType, cleaned_text)
        """
        lines = block_content.split("\n")

        # Check for heading
        first_line = lines[0].strip()
        if first_line.startswith("#"):
            # Extract heading text
            heading_text = re.sub(r"^#+\s+", "", first_line)
            return BlockType.HEADING, heading_text

        # Check for list (bullet or numbered)
        if first_line.startswith(("-", "*", "+")) or (lines[0] and lines[0][0].isdigit() and lines[0][1:3] == ". "):
            return BlockType.LIST, block_content

        # Check for code block
        if block_content.startswith("```") or block_content.startswith("~~~"):
            # Extract code content
            code_match = re.search(r"```[\w]*\n(.*?)\n```", block_content, re.DOTALL)
            if code_match:
                code_content = code_match.group(1)
            else:
                code_content = block_content
            return BlockType.TEXT, code_content

        # Default to text
        return BlockType.TEXT, block_content
