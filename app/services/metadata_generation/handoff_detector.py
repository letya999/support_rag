"""
HandoffDetector - Rule-based detection of cases requiring human operator handoff.

Uses regex patterns to identify questions that should be escalated to support team.
"""

import re
from typing import Dict, List, Optional, Tuple


class HandoffDetector:
    """
    Detects if a Q&A pair requires handoff to human operator.

    Uses regex patterns and answer length heuristics.
    No ML training required.
    """

    # Patterns: (regex_pattern, confidence_if_matched, clarifying_question)
    HANDOFF_PATTERNS = {
        r'contact\s+support|call\s+us|speak\s+to|talk\s+to|human\s+agent|operator|representative': (
            True, 0.95, "Would you like to speak with a support representative?"
        ),
        r"i'?m\s+sorry|apologize|unfortunately|regret|apologies": (
            True, 0.80, "I apologize for the inconvenience. Can I help further?"
        ),
        r'cannot\s+help|unable\s+to|can[\'t]+\s+support|don[\'t]+\s+support': (
            True, 0.75, "Let me escalate this to our support team."
        ),
        r'escalate|escalated|transfer|transferred': (
            True, 0.90, "Transferring to a support specialist..."
        ),
    }

    def __init__(self):
        """Initialize handoff detector."""
        pass

    def detect(
        self,
        question: str,
        answer: str
    ) -> Dict:
        """
        Detect if Q&A pair requires handoff to human operator.

        Args:
            question: The question text
            answer: The answer text

        Returns:
            Dict with:
                - requires_handoff: bool
                - confidence_threshold: float (confidence for this decision)
                - clarifying_questions: list of suggested follow-up questions
                - matched_pattern: the pattern that matched (if any)
        """
        combined_text = f"{question} {answer}".lower()

        max_confidence = 0.0
        matched_pattern = None
        clarifying_question = None

        # Check all patterns
        for pattern, (requires_handoff, confidence, question_text) in self.HANDOFF_PATTERNS.items():
            if re.search(pattern, combined_text):
                if confidence > max_confidence:
                    max_confidence = confidence
                    matched_pattern = pattern
                    clarifying_question = question_text

        # Heuristic: very short answers might indicate the AI couldn't answer
        if len(answer.strip()) < 30 and max_confidence == 0.0:
            max_confidence = 0.3
            matched_pattern = "short_answer"
            clarifying_question = "Would you like assistance from our support team?"

        # Determine final result
        requires_handoff = max_confidence > 0.5
        confidence_threshold = max_confidence if requires_handoff else 0.95

        clarifying_questions = []
        if clarifying_question:
            clarifying_questions.append(clarifying_question)

        return {
            "requires_handoff": requires_handoff,
            "confidence_threshold": confidence_threshold,
            "clarifying_questions": clarifying_questions,
            "matched_pattern": matched_pattern,
            "confidence": max_confidence
        }

    def detect_batch(
        self,
        qa_pairs: List[Dict[str, str]]
    ) -> List[Dict]:
        """
        Detect handoff for multiple Q&A pairs.

        Args:
            qa_pairs: List of {"question": "...", "answer": "..."} dicts

        Returns:
            List of handoff detection results
        """
        results = []
        for pair in qa_pairs:
            result = self.detect(pair["question"], pair["answer"])
            results.append(result)

        return results

    @staticmethod
    def get_pattern_stats(detection_results: List[Dict]) -> Dict:
        """Calculate statistics from detection results."""
        handoff_count = sum(1 for r in detection_results if r["requires_handoff"])
        pattern_counts = {}

        for result in detection_results:
            pattern = result.get("matched_pattern")
            if pattern:
                pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

        return {
            "total_items": len(detection_results),
            "handoff_count": handoff_count,
            "handoff_percentage": (
                (handoff_count / len(detection_results)) * 100
                if detection_results
                else 0.0
            ),
            "matched_patterns": pattern_counts
        }
