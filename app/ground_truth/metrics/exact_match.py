"""Exact Match Metric (Top-1 Accuracy)

Exact Match measures whether the top-1 ranked result contains
the correct answer.

Calculation: 1 if top-1 is correct, 0 otherwise
Average across all queries
"""

from typing import Dict, List, Any
from app.ground_truth.metrics.common import check_answer_in_chunk


def calculate_exact_match(
    expected_answer: str,
    retrieved_chunks: List[Dict[str, Any]]
) -> int:
    """
    Calculate Exact Match for a single query.

    Exact Match: 1 if top-1 result contains correct answer, 0 otherwise.

    Example:
        - Top-1 chunk contains answer → Exact Match = 1
        - Top-1 chunk doesn't contain answer → Exact Match = 0

    Args:
        expected_answer: The ground truth answer
        retrieved_chunks: List of retrieved chunks with "content" key
                         First item is top-1

    Returns:
        1 if top-1 matches, 0 otherwise

    Interpretation:
        - Measures top-1 ranking accuracy (most user-visible)
        - Target: > 0.7 (>70% of queries have correct answer at top-1)
        - Higher is better
        - Most strict metric (no credit for position 2, 3, etc.)
    """
    if not retrieved_chunks:
        return 0

    top_chunk = retrieved_chunks[0]["content"]
    return 1 if check_answer_in_chunk(expected_answer, top_chunk) else 0


def aggregate_exact_matches(exact_matches: List[int]) -> float:
    """
    Calculate average exact match across multiple queries.

    Args:
        exact_matches: List of individual exact match values (0 or 1)

    Returns:
        Average exact match (0.0 to 1.0)
    """
    if not exact_matches:
        return 0.0
    return sum(exact_matches) / len(exact_matches)
