"""Duplicate detection for Q&A pairs."""

import difflib
import logging
from typing import List, Tuple

from app.services.document_loaders import ProcessedQAPair, RawQAPair

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Detects and merges duplicate Q&A pairs."""

    FUZZY_THRESHOLD = 0.85  # Similarity threshold for fuzzy matching

    @classmethod
    def find_duplicates(cls, pairs: List[RawQAPair]) -> List[Tuple[int, int]]:
        """Find duplicate pairs in a list.

        Args:
            pairs: List of Q&A pairs

        Returns:
            List of (index1, index2) tuples indicating duplicates
        """
        duplicates = []

        for i in range(len(pairs)):
            for j in range(i + 1, len(pairs)):
                if cls._are_duplicate(pairs[i], pairs[j]):
                    duplicates.append((i, j))

        return duplicates

    @classmethod
    def remove_duplicates(cls, pairs: List[ProcessedQAPair]) -> List[ProcessedQAPair]:
        """Remove duplicates from list of processed pairs, keeping first occurrence.

        Args:
            pairs: List of processed Q&A pairs

        Returns:
            List with duplicates removed
        """
        seen_questions = {}
        unique_pairs = []

        for pair in pairs:
            q_normalized = cls._normalize_question(pair.question)

            # Check if we've seen similar question
            duplicate_found = False
            for seen_q, idx in seen_questions.items():
                if cls._are_questions_similar(q_normalized, seen_q):
                    logger.debug(
                        f"Removing duplicate of: {pair.question[:50]}..."
                    )
                    duplicate_found = True
                    break

            if not duplicate_found:
                seen_questions[q_normalized] = len(unique_pairs)
                unique_pairs.append(pair)

        logger.info(
            f"Removed {len(pairs) - len(unique_pairs)} duplicates "
            f"from {len(pairs)} pairs"
        )
        return unique_pairs

    @classmethod
    def _are_duplicate(cls, pair1: RawQAPair, pair2: RawQAPair) -> bool:
        """Check if two pairs are duplicates.

        Args:
            pair1: First pair
            pair2: Second pair

        Returns:
            True if pairs are duplicates
        """
        # Exact match (normalized)
        q1_norm = cls._normalize_question(pair1.question)
        q2_norm = cls._normalize_question(pair2.question)

        if q1_norm == q2_norm:
            return True

        # Fuzzy match
        if cls._are_questions_similar(q1_norm, q2_norm):
            return True

        return False

    @classmethod
    def _are_questions_similar(cls, q1: str, q2: str) -> bool:
        """Check if two questions are similar using fuzzy matching.

        Args:
            q1: First question (normalized)
            q2: Second question (normalized)

        Returns:
            True if questions are similar
        """
        similarity = difflib.SequenceMatcher(None, q1, q2).ratio()
        return similarity >= cls.FUZZY_THRESHOLD

    @staticmethod
    def _normalize_question(question: str) -> str:
        """Normalize question for comparison.

        Args:
            question: Question to normalize

        Returns:
            Normalized question
        """
        # Lowercase
        text = question.lower()

        # Remove extra whitespace
        text = " ".join(text.split())

        # Remove trailing punctuation
        text = text.rstrip("?.!,;:")

        return text
