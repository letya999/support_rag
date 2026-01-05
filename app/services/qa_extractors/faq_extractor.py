"""Q&A extractor for FAQ style documents."""

import logging
import re
from typing import List

from app.services.document_loaders import DocumentStructure, RawQAPair

from .base_extractor import BaseQAExtractor

logger = logging.getLogger(__name__)


class FAQExtractor(BaseQAExtractor):
    """Extracts Q&A pairs from FAQ style format (Q: ... A: ...)."""

    def extract(self, blocks: List, structure: DocumentStructure) -> List[RawQAPair]:
        """Extract Q&A pairs from FAQ formatted text.

        Args:
            blocks: List of document blocks
            structure: Document structure

        Returns:
            List of extracted Q&A pairs
        """
        pairs = []

        # Reconstruct text from blocks
        text_parts = []
        for block in blocks:
            if isinstance(block.content, str):
                text_parts.append(block.content)

        if not text_parts:
            return pairs

        full_text = "\n".join(text_parts)

        # Extract FAQ pairs
        qa_pairs = self._extract_faq_pairs(full_text)

        for question, answer in qa_pairs:
            question_clean = self._clean_text(question)
            answer_clean = self._clean_text(answer)

            if not self._is_valid_qa_pair(question_clean, answer_clean):
                logger.debug(
                    f"Skipping invalid FAQ pair: "
                    f"q_len={len(question_clean)}, a_len={len(answer_clean)}"
                )
                continue

            pair = RawQAPair(
                question=question_clean,
                answer=answer_clean,
                source_block_ids=[],
                extraction_method="faq_prefix_extraction",
                confidence=0.80,
                metadata={},
            )
            pairs.append(pair)

        logger.info(f"Extracted {len(pairs)} Q&A pairs from FAQ format")
        return pairs

    @staticmethod
    def _extract_faq_pairs(text: str) -> List[tuple]:
        """Extract Q&A pairs from FAQ text.

        Args:
            text: Text to parse

        Returns:
            List of (question, answer) tuples
        """
        pairs = []

        # Pattern 1: Q: ... A: ... format
        # This pattern captures Q: or Question: followed by text up to A: or Answer:
        pattern1 = r"[Qq](?:uestion)?[\s:\.]*(.+?)(?=[Aa](?:nswer)?[\s:\.]\s|$)"

        sections = re.split(r"[Aa](?:nswer)?[\s:\.]\s*", text)

        # Process alternating Q/A sections
        for i in range(0, len(sections) - 1, 2):
            q_section = sections[i]
            a_section = sections[i + 1]

            # Extract question (take last line as main question)
            q_lines = q_section.strip().split("\n")
            for q_line in reversed(q_lines):
                q_line = q_line.strip()
                # Remove Q: prefix
                q_line = re.sub(r"^[Qq](?:uestion)?[\s:\.]*", "", q_line)
                if q_line:
                    question = q_line
                    break
            else:
                continue

            # Extract answer (take text until next Q or end)
            a_text = a_section.split("\n")[0].strip()
            a_text = re.sub(r"^[Aa](?:nswer)?[\s:\.]*", "", a_text)

            if question and a_text:
                pairs.append((question, a_text))

        return pairs
