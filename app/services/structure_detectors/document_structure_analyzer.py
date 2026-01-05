"""Analyzes document structure to detect Q&A format patterns."""

import logging
from typing import List

from app.services.document_loaders import Block, BlockType, DocumentContent, DocumentStructure

from .pattern_matcher import PatternMatcher

logger = logging.getLogger(__name__)


class DocumentStructureAnalyzer:
    """Analyzes document structure to identify Q&A format."""

    def analyze(self, document: DocumentContent) -> DocumentStructure:
        """Analyze document and detect structure format.

        Args:
            document: Loaded document with blocks

        Returns:
            DocumentStructure with detected format and confidence
        """
        logger.info(f"Analyzing structure of {document.file_name}")

        # Try different structure detection methods
        detections = []

        # Check for table format (CSV or table-based)
        table_result = self._check_table_format(document)
        if table_result:
            detections.append(table_result)

        # Check for FAQ style (Q: A: pattern)
        faq_result = self._check_faq_format(document)
        if faq_result:
            detections.append(faq_result)

        # Check for list format (alternating Q/A)
        list_result = self._check_list_format(document)
        if list_result:
            detections.append(list_result)

        # Check for section format (heading-based)
        section_result = self._check_section_format(document)
        if section_result:
            detections.append(section_result)

        # Check for markdown format
        md_result = self._check_markdown_format(document)
        if md_result:
            detections.append(md_result)

        # Get best detection
        if detections:
            detections.sort(key=lambda x: x["confidence"], reverse=True)
            best = detections[0]

            structure = DocumentStructure(
                detected_format=best["format"],
                confidence=best["confidence"],
                column_mapping=best.get("column_mapping", {}),
                block_assignments=best.get("block_assignments", []),
                notes=[
                    f"Detected format: {best['format']} with {best['confidence']:.1%} confidence",
                    f"Found {best.get('pair_count', 0)} potential Q&A blocks",
                ] + best.get("notes", []),
            )
        else:
            structure = DocumentStructure(
                detected_format="unknown",
                confidence=0.0,
                notes=["Could not detect clear Q&A format. Defaulting to free text."],
            )

        logger.info(
            f"Detected format: {structure.detected_format} "
            f"(confidence: {structure.confidence:.1%})"
        )

        return structure

    @staticmethod
    def _check_table_format(document: DocumentContent) -> dict:
        """Check if document is primarily table-based Q&A.

        Args:
            document: Document to analyze

        Returns:
            Detection result dict or None
        """
        tables = [b for b in document.blocks if b.type == BlockType.TABLE]

        if not tables:
            return None

        # Analyze first table
        table = tables[0].content

        if not isinstance(table, list) or len(table) < 2:
            return None

        rows = table
        cols = len(rows[0]) if rows else 0

        # Look for Q/A patterns in headers
        header = rows[0]
        column_mapping = DocumentStructureAnalyzer._map_qa_columns(header)

        if not column_mapping:
            return None

        pair_count = len(rows) - 1  # Exclude header

        return {
            "format": "table",
            "confidence": 0.85 if "question" in column_mapping.values() and "answer" in column_mapping.values() else 0.6,
            "column_mapping": column_mapping,
            "pair_count": pair_count,
            "notes": [f"Found table with {pair_count} rows, {cols} columns"],
        }

    @staticmethod
    def _check_faq_format(document: DocumentContent) -> dict:
        """Check if document has FAQ style (Q: ... A: ...).

        Args:
            document: Document to analyze

        Returns:
            Detection result dict or None
        """
        text = document.raw_text

        if not PatternMatcher.has_faq_style_format(text):
            return None

        pairs = PatternMatcher.extract_faq_pairs(text)

        if len(pairs) < 2:
            return None

        return {
            "format": "faq",
            "confidence": 0.75,
            "pair_count": len(pairs),
            "notes": [f"Detected FAQ style with {len(pairs)} Q&A pairs"],
        }

    @staticmethod
    def _check_list_format(document: DocumentContent) -> dict:
        """Check if document has list-based Q&A format.

        Args:
            document: Document to analyze

        Returns:
            Detection result dict or None
        """
        list_blocks = [b for b in document.blocks if b.type == BlockType.LIST]

        if not list_blocks:
            return None

        # Check if lists contain question indicators
        question_blocks = 0
        for block in list_blocks:
            if isinstance(block.content, str):
                if PatternMatcher.has_question_indicator(block.content):
                    question_blocks += 1

        if question_blocks < 1:
            return None

        return {
            "format": "list",
            "confidence": 0.65,
            "pair_count": question_blocks,
            "notes": [f"Detected list format with {question_blocks} potential question blocks"],
        }

    @staticmethod
    def _check_section_format(document: DocumentContent) -> dict:
        """Check if Q&A pairs are in section format (heading-based).

        Args:
            document: Document to analyze

        Returns:
            Detection result dict or None
        """
        headings = [b for b in document.blocks if b.type == BlockType.HEADING]

        if len(headings) < 2:
            return None

        # Check if headings contain questions
        question_headings = 0
        for heading in headings:
            if isinstance(heading.content, str):
                if PatternMatcher.has_question_indicator(heading.content):
                    question_headings += 1

        confidence = question_headings / len(headings) if headings else 0

        if confidence < 0.3:  # Less than 30% of headings are questions
            return None

        return {
            "format": "sections",
            "confidence": 0.6 + (confidence * 0.25),
            "pair_count": question_headings,
            "notes": [
                f"Detected section format with {question_headings}/{len(headings)} question headings"
            ],
        }

    @staticmethod
    def _check_markdown_format(document: DocumentContent) -> dict:
        """Check if document is markdown with Q&A structure.

        Args:
            document: Document to analyze

        Returns:
            Detection result dict or None
        """
        if document.file_type.value != "md":
            return None

        headings = [b for b in document.blocks if b.type == BlockType.HEADING]

        if len(headings) < 1:
            return None

        return {
            "format": "markdown",
            "confidence": 0.7,
            "pair_count": len(headings),
            "notes": [f"Markdown document with {len(headings)} headings"],
        }

    @staticmethod
    def _map_qa_columns(header: List[str]) -> dict:
        """Map table columns to Q/A based on header content.

        Args:
            header: Table header row

        Returns:
            Dict mapping column index to role (question, answer, metadata, other)
        """
        mapping = {}

        header_lower = [str(h).lower().strip() for h in header]

        for idx, col_name in enumerate(header_lower):
            if any(
                kw in col_name for kw in ["question", "q.", "q:", "ask", "query"]
            ):
                mapping[idx] = "question"
            elif any(
                kw in col_name for kw in ["answer", "a.", "a:", "response", "reply"]
            ):
                mapping[idx] = "answer"
            elif any(
                kw in col_name for kw in ["category", "intent", "metadata", "notes"]
            ):
                mapping[idx] = "metadata"
            else:
                mapping[idx] = "other"

        return mapping
