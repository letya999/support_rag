"""Format validation for Q&A pairs."""

import logging
import re

from app.services.document_loaders import RawQAPair, ValidationResult

logger = logging.getLogger(__name__)


class FormatValidator:
    """Validates Q&A pair format and basic requirements."""

    # Configuration
    MIN_QUESTION_LENGTH = 5
    MAX_QUESTION_LENGTH = 500
    MIN_ANSWER_LENGTH = 10
    MAX_ANSWER_LENGTH = 5000

    @classmethod
    def validate(cls, pair: RawQAPair) -> ValidationResult:
        """Validate Q&A pair format.

        Args:
            pair: Raw Q&A pair to validate

        Returns:
            ValidationResult with errors/warnings
        """
        errors = []
        warnings = []
        confidence = 1.0

        # Check if both fields exist
        if not pair.question or not pair.question.strip():
            errors.append("Question is empty")
        if not pair.answer or not pair.answer.strip():
            errors.append("Answer is empty")

        if errors:
            return ValidationResult(is_valid=False, errors=errors, confidence=0.0)

        # Check lengths
        q_len = len(pair.question.strip())
        a_len = len(pair.answer.strip())

        if q_len < cls.MIN_QUESTION_LENGTH:
            errors.append(f"Question too short ({q_len} < {cls.MIN_QUESTION_LENGTH})")
            confidence -= 0.3

        if q_len > cls.MAX_QUESTION_LENGTH:
            errors.append(f"Question too long ({q_len} > {cls.MAX_QUESTION_LENGTH})")
            confidence -= 0.2

        if a_len < cls.MIN_ANSWER_LENGTH:
            errors.append(f"Answer too short ({a_len} < {cls.MIN_ANSWER_LENGTH})")
            confidence -= 0.3

        if a_len > cls.MAX_ANSWER_LENGTH:
            warnings.append(f"Answer very long ({a_len} > {cls.MAX_ANSWER_LENGTH})")
            confidence -= 0.1

        # Check for excessive repeated characters
        if cls._has_excessive_repetition(pair.question):
            errors.append("Question has excessive character repetition")
            confidence -= 0.2

        if cls._has_excessive_repetition(pair.answer):
            errors.append("Answer has excessive character repetition")
            confidence -= 0.2

        # Check for common error values
        if cls._looks_like_error(pair.answer):
            errors.append("Answer looks like an error message or null value")
            confidence -= 0.4

        # Check for control characters
        if cls._has_many_control_chars(pair.question):
            warnings.append("Question has control characters")
            confidence -= 0.1

        if cls._has_many_control_chars(pair.answer):
            warnings.append("Answer has control characters")
            confidence -= 0.1

        is_valid = len(errors) == 0
        confidence = max(0.0, confidence)

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            confidence=confidence
        )

    @staticmethod
    def _has_excessive_repetition(text: str, threshold: int = 5) -> bool:
        """Check if text has excessive character repetition.

        Args:
            text: Text to check
            threshold: Max consecutive repetitions allowed

        Returns:
            True if excessive repetition found
        """
        return bool(re.search(rf"(.)\1{{{threshold},}}", text))

    @staticmethod
    def _looks_like_error(text: str) -> bool:
        """Check if text looks like an error message.

        Args:
            text: Text to check

        Returns:
            True if text looks like error
        """
        error_patterns = [
            r"error",
            r"exception",
            r"undefined",
            r"null",
            r"none",
            r"n/a",
            r"na",
            r"\[blank\]",
            r"\[empty\]",
            r"404",
            r"500",
        ]

        text_lower = text.lower().strip()

        # Exact matches for short texts
        if text_lower in ["error", "null", "none", "undefined", "n/a", "na"]:
            return True

        # Pattern matching
        for pattern in error_patterns:
            if re.search(f"^{pattern}$", text_lower):
                return True

        return False

    @staticmethod
    def _has_many_control_chars(text: str, threshold: float = 0.05) -> bool:
        """Check if text has too many control characters.

        Args:
            text: Text to check
            threshold: Fraction of control characters allowed (0-1)

        Returns:
            True if too many control chars
        """
        if not text:
            return False

        control_count = sum(1 for ch in text if not ch.isprintable() and ch not in "\n\r\t ")
        control_ratio = control_count / len(text)

        return control_ratio > threshold
