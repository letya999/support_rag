"""Q&A extractor for list-based documents."""

import logging
import re
from typing import List

from app.services.document_loaders import Block, BlockType, DocumentStructure, RawQAPair
from app.services.structure_detectors import PatternMatcher

from .base_extractor import BaseQAExtractor

logger = logging.getLogger(__name__)


class ListQAExtractor(BaseQAExtractor):
    """Extracts Q&A pairs from list format documents."""

    def extract(self, blocks: List[Block], structure: DocumentStructure) -> List[RawQAPair]:
        """Extract Q&A pairs from list blocks.

        Args:
            blocks: List of document blocks
            structure: Document structure

        Returns:
            List of extracted Q&A pairs
        """
        pairs = []

        # Get all list blocks
        list_blocks = [b for b in blocks if b.type == BlockType.LIST]

        # Also include text blocks as they might contain questions
        text_blocks = [b for b in blocks if b.type == BlockType.TEXT]

        all_blocks = list_blocks + text_blocks

        for block in all_blocks:
            if not isinstance(block.content, str):
                continue

            # Split content into lines
            lines = block.content.split("\n")

            # Try different pairing patterns
            extracted = self._extract_alternating_pairs(lines, block.original_index)
            pairs.extend(extracted)

            extracted = self._extract_grouped_pairs(lines, block.original_index)
            pairs.extend(extracted)

        logger.info(f"Extracted {len(pairs)} Q&A pairs from list format")
        return pairs

    def _extract_alternating_pairs(self, lines: List[str], block_id: int) -> List[RawQAPair]:
        """Extract pairs from alternating Q/A lines.

        Pattern:
        • Question text?
        • Answer text

        Args:
            lines: Text lines
            block_id: Source block ID

        Returns:
            List of extracted pairs
        """
        pairs = []
        i = 0

        while i < len(lines) - 1:
            line1 = lines[i].strip()
            line2 = lines[i + 1].strip() if i + 1 < len(lines) else ""

            # Remove list markers
            line1_clean = re.sub(r"^[•\-\*\+]\s+|\^\d+\.\s+", "", line1)
            line2_clean = re.sub(r"^[•\-\*\+]\s+|\^\d+\.\s+", "", line2)

            if not line1_clean or not line2_clean:
                i += 1
                continue

            # Check if line1 looks like a question
            if PatternMatcher.has_question_indicator(line1_clean):
                question = self._clean_text(line1_clean)
                answer = self._clean_text(line2_clean)

                if self._is_valid_qa_pair(question, answer):
                    pair = RawQAPair(
                        question=question,
                        answer=answer,
                        source_block_ids=[block_id],
                        extraction_method="list_alternating_pairs",
                        confidence=0.75,
                    )
                    pairs.append(pair)
                    i += 2
                    continue

            i += 1

        return pairs

    def _extract_grouped_pairs(self, lines: List[str], block_id: int) -> List[RawQAPair]:
        """Extract pairs from grouped Q/A blocks separated by empty lines.

        Pattern:
        Question text here?
        More question details

        Answer text starts here.
        Answer continues here.

        Args:
            lines: Text lines
            block_id: Source block ID

        Returns:
            List of extracted pairs
        """
        pairs = []

        # Split by empty lines
        groups = []
        current_group = []

        for line in lines:
            if line.strip():
                current_group.append(line.strip())
            else:
                if current_group:
                    groups.append(current_group)
                    current_group = []

        if current_group:
            groups.append(current_group)

        # Try to pair consecutive groups
        i = 0
        while i < len(groups) - 1:
            group1_text = " ".join(groups[i])
            group2_text = " ".join(groups[i + 1])

            # Check if group1 looks like a question
            if PatternMatcher.has_question_indicator(group1_text):
                question = self._clean_text(group1_text)
                answer = self._clean_text(group2_text)

                if self._is_valid_qa_pair(question, answer):
                    pair = RawQAPair(
                        question=question,
                        answer=answer,
                        source_block_ids=[block_id],
                        extraction_method="list_grouped_pairs",
                        confidence=0.70,
                    )
                    pairs.append(pair)
                    i += 2
                    continue

            i += 1

        return pairs
