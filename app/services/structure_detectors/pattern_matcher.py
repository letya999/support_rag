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
        r"^Вопрос[:.]?\s+",
        r"^[ВB][:.]?\s+",  # Cyrillic and Latin
        r"^\d+\.\s+",  # Numbered questions
        r"^●\s+",  # Bullet points
        r"^•\s+",
    ]

    ANSWER_PREFIXES = [
        r"^A[:.]?\s+",
        r"^Answer[:.]?\s+",
        r"^Ответ[:.]?\s+",
        r"^[АО][:.]?\s+",  # Cyrillic and Latin
    ]

    QUESTION_INDICATORS = [
        "How ", "What ", "Where ", "When ", "Why ", "Which ", "Is ", "Are ",
        "Can ", "Could ", "Will ", "Would ", "Should ", "May ", "Might ", "Do ",
        "Does ", "Did ", "Has ", "Have ", "Had ", "Is there ", "Are there ",
        "Как ", "Что ", "Где ", "Когда ", "Почему ", "Кто ", "Чем ", "Как сделать",
        "Как настроить", "Является ли", "Могу ли", "Нужно ли",
    ]

    FAQ_STYLE_SEPARATORS = [
        r"\n\s*[Qq]\s*:",
        r"\n\s*[Qq]uestion\s*:",
        r"\n\s*[Вв]\s*:",
        r"\n\s*[Вв]опрос\s*:",
        r"\n\s*[Aa]\s*:",
        r"\n\s*[Aa]nswer\s*:",
        r"\n\s*[Оо]\s*:",
        r"\n\s*[Оо]твет\s*:",
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
        if any(text_lower.startswith(indicator.lower()) for indicator in cls.QUESTION_INDICATORS):
            return True
                
        return False

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

        # Pattern: Q: ... A: ... (Latin and Cyrillic)
        pattern = r"(?:[QqВв]|Question|Вопрос)\s*:?\s*(.+?)(?=(?:[AaОо]|Answer|Ответ)\s*:|\Z)\s*(?:[AaОо]|Answer|Ответ)\s*:?\s*(.+?)(?=(?:[QqВв]|Question|Вопрос)\s*:|\Z)"
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

        for question, answer in matches:
            q = question.strip()
            a = answer.strip()
            if q and a:
                pairs.append((q, a))

        return pairs

    @classmethod
    def extract_heuristic_pairs(cls, text: str) -> List[tuple]:
        """Extract pairs based on structural cues (short lines followed by long text).
        
        Args:
            text: Raw text from document
            
        Returns:
            List of (question, answer) tuples
        """
        pairs = []
        # Split into blocks by double newline or single newline if it looks like a header
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return []

        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Heuristic for Question/Header:
            # 1. Ends with ? (strong signal)
            # 2. Is short, starts with Upper case, and NO end punctuation (potential header)
            is_question = '?' in line
            is_header = len(line) < 100 and line[0].isupper() and not line.endswith(('.', '!', ':', ';'))
            
            if is_question or is_header:
                question = line
                answer_parts = []
                
                # Check for multi-line question (if next line also looks like part of a title/question)
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if '?' in next_line and len(next_line) < 100 and len(question) < 150:
                        question += " " + next_line
                        j += 1
                    else:
                        break
                
                # Collect the answer - it must be at least one line that looks like content
                while j < len(lines):
                    next_line = lines[j]
                    
                    # Does the next line look like a NEW question/header?
                    is_next_q = '?' in next_line
                    is_next_h = len(next_line) < 80 and next_line[0].isupper() and not next_line.endswith(('.', '!', ':', ';'))
                    
                    if is_next_q or is_next_h:
                        break
                    
                    answer_parts.append(next_line)
                    j += 1
                
                # Validation: Question shouldn't be too long, Answer shouldn't be empty
                if answer_parts and len(question) < 250:
                    answer = " ".join(answer_parts)
                    # Extra check: if the "answer" is just another short line, maybe it's not a real pair
                    if len(answer) > 20:
                        pairs.append((question, answer))
                        i = j
                        continue
            i += 1
            
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
