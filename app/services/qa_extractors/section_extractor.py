"""Q&A extractor for section/heading-based documents."""

import logging
from typing import List

from app.services.document_loaders import Block, BlockType, DocumentStructure, RawQAPair
from app.services.structure_detectors import PatternMatcher

from .base_extractor import BaseQAExtractor

logger = logging.getLogger(__name__)


class SectionQAExtractor(BaseQAExtractor):
    """Extracts Q&A pairs from section format (heading-based)."""

    def extract(self, blocks: List[Block], structure: DocumentStructure) -> List[RawQAPair]:
        """Extract Q&A pairs from heading-based sections.

        Format:
        ### How to reset password?
        To reset your password...

        ### What are the requirements?
        The requirements are...

        Args:
            blocks: List of document blocks
            structure: Document structure

        Returns:
            List of extracted Q&A pairs
        """
        pairs = []

        # Find heading blocks
        heading_blocks = [b for b in blocks if b.type == BlockType.HEADING]

        if not heading_blocks:
            logger.debug("No heading blocks found for section extraction")
            return pairs

        # For each heading, collect following text until next heading
        for i, heading_block in enumerate(heading_blocks):
            heading_text = heading_block.content
            if not isinstance(heading_text, str):
                continue

            # Check if heading looks like a question
            if not PatternMatcher.has_question_indicator(heading_text):
                logger.debug(f"Heading doesn't look like question: {heading_text[:50]}")
                continue

            # Collect text blocks following this heading
            answer_parts = []

            # Look for text blocks after this heading
            heading_idx = heading_block.original_index

            for block in blocks:
                if block.original_index <= heading_idx:
                    continue

                # Stop at next heading
                if block.type == BlockType.HEADING:
                    break

                # Collect text/list content
                if block.type in (BlockType.TEXT, BlockType.LIST):
                    if isinstance(block.content, str):
                        answer_parts.append(block.content)

            if not answer_parts:
                logger.debug(f"No answer content found for heading: {heading_text[:50]}")
                continue

            question = self._clean_text(heading_text)
            answer = self._clean_text(" ".join(answer_parts))

            if not self._is_valid_qa_pair(question, answer):
                logger.debug(
                    f"Skipping invalid section pair: "
                    f"q_len={len(question)}, a_len={len(answer)}"
                )
                continue

            pair = RawQAPair(
                question=question,
                answer=answer,
                source_block_ids=[heading_block.original_index],
                extraction_method="section_heading_extraction",
                confidence=0.80,
                metadata={"heading_level": heading_block.metadata.get("level", 1)},
            )
            pairs.append(pair)

        logger.info(f"Extracted {len(pairs)} Q&A pairs from section format")
        return pairs
