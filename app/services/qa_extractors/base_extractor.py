"""Base class for Q&A extractors."""

from abc import ABC, abstractmethod
from typing import List

from app.services.document_loaders import Block, DocumentStructure, RawQAPair


class BaseQAExtractor(ABC):
    """Abstract base class for Q&A pair extractors."""

    @abstractmethod
    def extract(self, blocks: List[Block], structure: DocumentStructure) -> List[RawQAPair]:
        """Extract Q&A pairs from document blocks.

        Args:
            blocks: List of document blocks
            structure: Analyzed document structure

        Returns:
            List of extracted Q&A pairs
        """
        pass

    @staticmethod
    def _clean_text(text: str) -> str:
        """Basic text cleaning.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove leading/trailing whitespace
        text = text.strip()

        # Replace multiple spaces with single space
        text = " ".join(text.split())

        # Remove control characters but keep newlines for structure
        text = "".join(ch if ch.isprintable() or ch in "\n\r\t" else "" for ch in text)

        return text.strip()

    @staticmethod
    def _is_valid_qa_pair(question: str, answer: str) -> bool:
        """Check if Q&A pair meets basic validity requirements.

        Args:
            question: Question text
            answer: Answer text

        Returns:
            True if pair seems valid
        """
        # Check minimum lengths
        if len(question.strip()) < 5:
            return False
        if len(answer.strip()) < 10:
            return False

        # Check maximum lengths
        if len(question) > 500:
            return False
        if len(answer) > 5000:
            return False

        # Check for too many repeated characters
        if "." * 10 in question or "." * 10 in answer:
            return False

        # Check for obvious errors
        if answer.lower() in ["error", "null", "undefined", "n/a", "na", ""]:
            return False

        return True
