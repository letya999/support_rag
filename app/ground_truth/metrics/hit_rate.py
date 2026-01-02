"""Hit Rate Metric (Recall@K)

Hit Rate measures the percentage of queries where the correct answer
is found in the top-K retrieved results.

Calculation: 1 if found in top-K, 0 otherwise
Average across all queries
"""

from typing import Dict, List, Any
from app.ground_truth.metrics.common import find_answer_position


def calculate_hit_rate(
    expected_answer: str,
    retrieved_chunks: List[Dict[str, Any]],
    top_k: int = 3
) -> int:
    """
    Calculate Hit Rate for a single query.

    Hit Rate (Recall@K): 1 if correct answer in top-K, 0 otherwise.

    Example:
        - Query finds answer at position 2 in top-3 → Hit Rate = 1
        - Query answer not found in top-3 → Hit Rate = 0

    Args:
        expected_answer: The ground truth answer
        retrieved_chunks: List of retrieved chunks with "content" key
        top_k: Number of top results to consider (default: 3)

    Returns:
        1 if answer found in top-K, 0 otherwise

    Interpretation:
        - Measures retrieval coverage
        - Target: > 0.9 (>90% of queries find correct answer)
        - Higher is better
    """
    position = find_answer_position(expected_answer, retrieved_chunks, top_k)
    return 1 if position > 0 else 0


def aggregate_hit_rates(hit_rates: List[int]) -> float:
    """
    Calculate average hit rate across multiple queries.

    Args:
        hit_rates: List of individual hit rate values (0 or 1)

    Returns:
        Average hit rate (0.0 to 1.0)
    """
    if not hit_rates:
        return 0.0
    return sum(hit_rates) / len(hit_rates)
