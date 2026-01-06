"""Text cleaning and normalization utilities."""

import html
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


class TextCleaner:
    """Utilities for cleaning and normalizing text."""

    # Common abbreviations to be aware of
    ABBREVIATIONS = {
        "i.e.": "that is",
        "e.g.": "for example",
        "etc.": "and so on",
        "etc": "and so on",
        "vs.": "versus",
        "vs": "versus",
        "approx.": "approximately",
        "Dr.": "Doctor",
        "Mr.": "Mister",
        "Mrs.": "Mrs",
        "Ms.": "Ms",
        "Prof.": "Professor",
    }

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text comprehensively.

        Args:
            text: Raw text to clean

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Normalize unicode
        text = unicodedata.normalize("NFKD", text)

        # Decode HTML entities
        text = html.unescape(text)

        # Remove control characters (except newlines/tabs)
        text = "".join(ch if ch.isprintable() or ch in "\n\r\t" else "" for ch in text)

        # Remove extra whitespace but preserve paragraph structure
        lines = text.split("\n")
        lines = [" ".join(line.split()) for line in lines]
        text = "\n".join(lines)

        # Remove excessive blank lines
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

        # Trim
        text = text.strip()

        return text

    @staticmethod
    def remove_markdown_formatting(text: str) -> str:
        """Remove markdown formatting from text.

        Args:
            text: Text with markdown

        Returns:
            Text without markdown formatting
        """
        # Remove bold/italic
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # **bold**
        text = re.sub(r"\*(.*?)\*", r"\1", text)  # *italic*
        text = re.sub(r"__(.*?)__", r"\1", text)  # __bold__
        text = re.sub(r"_(.*?)_", r"\1", text)  # _italic_

        # Remove links [text](url)
        text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)

        # Remove headers
        text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)

        # Remove code blocks
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # Remove list markers
        text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)

        return text

    @staticmethod
    def remove_html_tags(text: str) -> str:
        """Remove HTML tags from text.

        Args:
            text: Text with HTML

        Returns:
            Text without HTML tags
        """
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Remove multiple spaces
        text = re.sub(r"\s+", " ", text).strip()
        
        # Fix spaces before punctuation (common in PDF extraction)
        text = re.sub(r"\s+([,.!?;:])", r"\1", text)
        
        return text

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Normalize whitespace in text.

        Args:
            text: Text to normalize

        Returns:
            Text with normalized whitespace
        """
        # Replace multiple spaces with single space
        text = re.sub(r" +", " ", text)

        # Replace multiple newlines with double newline
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove spaces before punctuation
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)

        return text.strip()

    @staticmethod
    def remove_noise(text: str) -> str:
        """Remove common noise from text.

        Args:
            text: Text to clean

        Returns:
            Text without common noise
        """
        # Remove page numbers (Page 1, Page 2, etc)
        text = re.sub(r"Page\s+\d+\s*", "", text, flags=re.IGNORECASE)

        # Remove footer/header markers
        text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^_{3,}$", "", text, flags=re.MULTILINE)

        # Remove common metadata
        text = re.sub(r"Updated?:\s+.*?(?=\n|$)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"Version:\s+.*?(?=\n|$)", "", text, flags=re.IGNORECASE)

        return text

    @staticmethod
    def split_into_sentences(text: str) -> list:
        """Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Simple sentence splitter
        # This is a basic implementation; for production, consider NLTK or spaCy
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    @staticmethod
    def split_into_paragraphs(text: str) -> list:
        """Split text into paragraphs.

        Args:
            text: Text to split

        Returns:
            List of paragraphs
        """
        paragraphs = text.split("\n\n")
        return [p.strip() for p in paragraphs if p.strip()]
