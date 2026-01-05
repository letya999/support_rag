"""Confidence scoring for Q&A pairs."""

import logging
import re

from app.services.document_loaders import DocumentStructure, RawQAPair

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """Scores confidence of Q&A pairs based on multiple factors."""

    @classmethod
    def score_pair(cls, pair: RawQAPair, structure: DocumentStructure) -> float:
        """Calculate confidence score for a Q&A pair.

        Confidence factors (0.0-1.0):
        - Pattern matching accuracy: +0.25
        - Question indicators: +0.15
        - Answer logic: +0.15
        - Text quality: +0.15
        - Structure match: +0.15
        - Extraction method reliability: +0.15

        Args:
            pair: Q&A pair to score
            structure: Document structure context

        Returns:
            Confidence score (0.0-1.0)
        """
        score = 0.0

        # Start with extraction method confidence
        score += pair.confidence * 0.2

        # Pattern matching accuracy (based on extraction method)
        pattern_score = cls._score_pattern_matching(pair)
        score += pattern_score * 0.2

        # Question indicators
        q_score = cls._score_question_quality(pair.question)
        score += q_score * 0.15

        # Answer indicators
        a_score = cls._score_answer_quality(pair.answer)
        score += a_score * 0.15

        # Text quality
        quality_score = cls._score_text_quality(pair)
        score += quality_score * 0.15

        # Structure alignment
        structure_score = cls._score_structure_alignment(pair, structure)
        score += structure_score * 0.15

        # Normalize to 0-1 range
        score = max(0.0, min(1.0, score))

        return score

    @staticmethod
    def _score_pattern_matching(pair: RawQAPair) -> float:
        """Score based on how well pattern was matched.

        Args:
            pair: Q&A pair

        Returns:
            Score 0-1
        """
        method = pair.extraction_method

        # Some methods are inherently more reliable
        method_scores = {
            "table_row_extraction": 0.9,
            "faq_prefix_extraction": 0.85,
            "section_heading_extraction": 0.80,
            "list_alternating_pairs": 0.75,
            "list_grouped_pairs": 0.70,
            "markdown_section_extraction": 0.80,
            "two_column_extraction": 0.65,
        }

        return method_scores.get(method, 0.6)

    @staticmethod
    def _score_question_quality(question: str) -> float:
        """Score how well-formed the question is.

        Args:
            question: Question text

        Returns:
            Score 0-1
        """
        score = 0.5

        # Question mark
        if "?" in question:
            score += 0.2

        # Question words
        question_words = {
            "how", "what", "where", "when", "why", "which",
            "is", "are", "can", "could", "will", "would",
            "should", "may", "might", "do", "does", "did",
            "has", "have", "had"
        }

        first_word = question.split()[0].lower() if question.split() else ""
        if first_word in question_words:
            score += 0.15

        # Reasonable length
        if 5 < len(question) < 200:
            score += 0.15

        return min(1.0, score)

    @staticmethod
    def _score_answer_quality(answer: str) -> float:
        """Score how well-formed the answer is.

        Args:
            answer: Answer text

        Returns:
            Score 0-1
        """
        score = 0.5

        # Answer is a statement (not a question)
        if not answer.endswith("?"):
            score += 0.15

        # Answer is substantial (more than a word)
        if len(answer.split()) > 3:
            score += 0.15

        # Reasonable length
        if 10 < len(answer) < 1000:
            score += 0.20

        return min(1.0, score)

    @staticmethod
    def _score_text_quality(pair: RawQAPair) -> float:
        """Score text quality (no errors, clean).

        Args:
            pair: Q&A pair

        Returns:
            Score 0-1
        """
        score = 0.7

        # No excessive punctuation
        if not re.search(r"([!?.]){4,}", pair.question + pair.answer):
            score += 0.15

        # No obvious errors
        error_terms = {"error", "null", "undefined", "n/a"}
        combined = (pair.question + " " + pair.answer).lower()
        if not any(term in combined for term in error_terms):
            score += 0.15

        return min(1.0, score)

    @staticmethod
    def _score_structure_alignment(pair: RawQAPair, structure: DocumentStructure) -> float:
        """Score how well pair aligns with detected structure.

        Args:
            pair: Q&A pair
            structure: Detected document structure

        Returns:
            Score 0-1
        """
        score = 0.6

        # Check if extraction method matches structure
        extraction_method = pair.extraction_method
        structure_format = structure.detected_format

        matches = {
            ("table_row_extraction", "table"): 0.3,
            ("faq_prefix_extraction", "faq"): 0.3,
            ("list_alternating_pairs", "list"): 0.25,
            ("list_grouped_pairs", "list"): 0.25,
            ("section_heading_extraction", "sections"): 0.25,
            ("markdown_section_extraction", "markdown"): 0.25,
            ("two_column_extraction", "two_column"): 0.25,
        }

        bonus = matches.get((extraction_method, structure_format), 0)
        score += bonus

        return min(1.0, score)
