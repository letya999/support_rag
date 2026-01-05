"""Q&A extractor for two-column layout documents."""

import logging
from typing import List

from app.services.document_loaders import Block, BlockType, DocumentStructure, RawQAPair
from app.services.structure_detectors import PatternMatcher

from .base_extractor import BaseQAExtractor

logger = logging.getLogger(__name__)


class TwoColumnExtractor(BaseQAExtractor):
    """Extracts Q&A pairs from documents with two-column layout.

    This is primarily useful for PDF documents with left column = questions,
    right column = answers layout.
    """

    def extract(self, blocks: List[Block], structure: DocumentStructure) -> List[RawQAPair]:
        """Extract Q&A pairs from two-column layout.

        Note: This is a simplified implementation. Real PDF two-column detection
        would require analyzing X-coordinates of text blocks.

        Args:
            blocks: List of document blocks
            structure: Document structure

        Returns:
            List of extracted Q&A pairs
        """
        pairs = []

        # Simplified approach: try to detect Q/A split in text blocks
        # by looking for patterns where text before a marker is questions
        # and text after is answers

        text_blocks = [b for b in blocks if b.type == BlockType.TEXT]

        if len(text_blocks) < 2:
            return pairs

        # Try to split blocks into Q and A halves
        mid_point = len(text_blocks) // 2

        question_blocks = text_blocks[:mid_point]
        answer_blocks = text_blocks[mid_point:]

        # Extract questions from first half
        questions = []
        for block in question_blocks:
            if isinstance(block.content, str):
                lines = block.content.split("\n")
                for line in lines:
                    line = line.strip()
                    if line and PatternMatcher.has_question_indicator(line):
                        questions.append(self._clean_text(line))

        # Extract answers from second half
        answers = []
        for block in answer_blocks:
            if isinstance(block.content, str):
                lines = block.content.split("\n")
                for line in lines:
                    line = line.strip()
                    if line:
                        answers.append(self._clean_text(line))

        # Pair up questions and answers
        for i, question in enumerate(questions):
            if i < len(answers):
                answer = answers[i]

                if self._is_valid_qa_pair(question, answer):
                    pair = RawQAPair(
                        question=question,
                        answer=answer,
                        source_block_ids=[],
                        extraction_method="two_column_extraction",
                        confidence=0.65,
                    )
                    pairs.append(pair)

        logger.info(f"Extracted {len(pairs)} Q&A pairs from two-column format")
        return pairs
