"""Semantic validation for Q&A pairs."""

import logging
from typing import Set

from app.services.document_loaders import RawQAPair, ValidationResult

logger = logging.getLogger(__name__)


class SemanticValidator:
    """Validates semantic correctness of Q&A pairs."""

    QUESTION_WORDS = {
        "how", "what", "where", "when", "why", "which",
        "is", "are", "can", "could", "will", "would",
        "should", "may", "might", "do", "does", "did",
        "has", "have", "had", "am", "be", "being",
        "was", "were", "should"
    }

    @classmethod
    def validate(cls, pair: RawQAPair) -> ValidationResult:
        """Validate semantic correctness of Q&A pair.

        Args:
            pair: Q&A pair to validate

        Returns:
            ValidationResult with errors/warnings
        """
        errors = []
        warnings = []
        confidence = 1.0

        # Check if question looks like a question
        if not cls._is_question(pair.question):
            warnings.append("Question doesn't contain typical question indicators")
            confidence -= 0.2

        # Check if answer is not a question
        if cls._is_question(pair.answer):
            errors.append("Answer looks like a question, not an answer")
            confidence -= 0.3

        # Check answer is longer than question (usually)
        if len(pair.answer) < len(pair.question):
            warnings.append("Answer is shorter than question")
            confidence -= 0.1

        # Check for semantic relationship (word overlap)
        overlap = cls._get_word_overlap(pair.question, pair.answer)
        if overlap < 0.1:
            warnings.append("Low word overlap between question and answer")
            confidence -= 0.15
        elif overlap > 0.8:
            warnings.append("High word overlap between question and answer (possible repetition)")
            confidence -= 0.1

        is_valid = len(errors) == 0
        confidence = max(0.0, min(1.0, confidence))

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            confidence=confidence
        )

    @classmethod
    def _is_question(cls, text: str) -> bool:
        """Check if text looks like a question.

        Args:
            text: Text to check

        Returns:
            True if text is likely a question
        """
        text = text.strip()

        # Check for question mark
        if text.endswith("?"):
            return True

        # Check for question words at start
        first_word = text.split()[0].lower() if text.split() else ""
        if first_word in cls.QUESTION_WORDS:
            return True

        # Check for question word anywhere
        words = text.lower().split()
        if any(word in cls.QUESTION_WORDS for word in words):
            return True

        return False

    @staticmethod
    def _get_word_overlap(text1: str, text2: str) -> float:
        """Calculate word overlap between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Overlap ratio (0-1)
        """
        # Extract words (lowercase, remove punctuation)
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0
