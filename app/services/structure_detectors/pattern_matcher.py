"""Pattern matching utilities for detecting Q&A structures."""

import re
from typing import List, NamedTuple, Optional


class PatternMatch(NamedTuple):
    """Result of pattern matching."""

    pattern_name: str
    text: str
    position: int
    confidence: float


class PatternMatcher:
    """Matcher for detecting Q&A indicator patterns."""

    # Common Q&A prefixes and indicators
    QUESTION_PREFIXES = [
        r"^Q[:.]?\s+",
        r"^Question[:.]?\s+",
        r"^\d+\.\s+",  # Numbered questions
        r"^●\s+",  # Bullet points
        r"^•\s+",
    ]

    ANSWER_PREFIXES = [
        r"^A[:.]?\s+",
        r"^Answer[:.]?\s+",
    ]

    QUESTION_INDICATORS = [
        "How ",
        "What ",
        "Where ",
        "When ",
        "Why ",
        "Which ",
        "Is ",
        "Are ",
        "Can ",
        "Could ",
        "Will ",
        "Would ",
        "Should ",
        "May ",
        "Might ",
        "Do ",
        "Does ",
        "Did ",
        "Has ",
        "Have ",
        "Had ",
        "Is there ",
        "Are there ",
    ]

    FAQ_STYLE_SEPARATORS = [
        r"\n\s*[Qq]\s*:",
        r"\n\s*[Qq]uestion\s*:",
        r"\n\s*[Aa]\s*:",
        r"\n\s*[Aa]nswer\s*:",
    ]

    @classmethod
    def find_qa_indicators(cls, text: str) -> List[PatternMatch]:
        """Find Q&A indicator patterns in text.

        Args:
            text: Text to search

        Returns:
            List of pattern matches
        """
        matches = []

        # Find question prefixes
        for prefix_pattern in cls.QUESTION_PREFIXES:
            for match in re.finditer(prefix_pattern, text, re.MULTILINE | re.IGNORECASE):
                matches.append(
                    PatternMatch(
                        pattern_name="question_prefix",
                        text=match.group(),
                        position=match.start(),
                        confidence=0.8,
                    )
                )

        # Find answer prefixes
        for prefix_pattern in cls.ANSWER_PREFIXES:
            for match in re.finditer(prefix_pattern, text, re.MULTILINE | re.IGNORECASE):
                matches.append(
                    PatternMatch(
                        pattern_name="answer_prefix",
                        text=match.group(),
                        position=match.start(),
                        confidence=0.8,
                    )
                )

        # Find question indicator words
        for indicator in cls.QUESTION_INDICATORS:
            for match in re.finditer(re.escape(indicator), text, re.IGNORECASE):
                matches.append(
                    PatternMatch(
                        pattern_name="question_indicator",
                        text=match.group(),
                        position=match.start(),
                        confidence=0.6,
                    )
                )

        return matches

    @classmethod
    def has_question_indicator(cls, text: str) -> bool:
        """Check if text contains any question indicators.

        Args:
            text: Text to check

        Returns:
            True if text looks like a question
        """
        # Check for question mark
        if "?" in text:
            return True

        # Check for question words
        text_lower = text.lower()
        return any(text_lower.startswith(indicator.lower()) for indicator in cls.QUESTION_INDICATORS)

    @classmethod
    def has_faq_style_format(cls, text: str) -> bool:
        """Check if text has FAQ style (Q: ... A: ... format).

        Args:
            text: Text to check

        Returns:
            True if text appears to be in FAQ style
        """
        for separator in cls.FAQ_STYLE_SEPARATORS:
            if re.search(separator, text):
                return True
        return False

    @classmethod
    def extract_faq_pairs(cls, text: str) -> List[tuple]:
        """Extract Q&A pairs from FAQ-style text.

        Args:
            text: Text in FAQ format

        Returns:
            List of (question, answer) tuples
        """
        pairs = []

        # Pattern: Q: ... A: ...
        pattern = r"[Qq]\s*:?\s*(.+?)(?=[Aa]\s*:|\Z)\s*[Aa]\s*:?\s*(.+?)(?=[Qq]\s*:|\Z)"
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

        for question, answer in matches:
            q = question.strip()
            a = answer.strip()
            if q and a:
                pairs.append((q, a))

        return pairs

    @classmethod
    def find_heading_boundaries(cls, lines: List[str]) -> List[tuple]:
        """Find headings and their content boundaries.

        Args:
            lines: List of text lines

        Returns:
            List of (start_idx, end_idx, heading_text) tuples
        """
        boundaries = []
        heading_pattern = re.compile(r"^#+\s+(.+)$")

        for idx, line in enumerate(lines):
            match = heading_pattern.match(line)
            if match:
                heading_text = match.group(1)
                boundaries.append((idx, heading_text))

        # Convert to ranges
        ranges = []
        for i, (start_idx, heading_text) in enumerate(boundaries):
            end_idx = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(lines)
            ranges.append((start_idx, end_idx, heading_text))

        return ranges
