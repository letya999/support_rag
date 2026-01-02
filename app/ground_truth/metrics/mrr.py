"""MRR Metric (Mean Reciprocal Rank)

MRR measures the average reciprocal position of the correct answer
in the retrieved results. Penalizes lower positions.

Position 1 → 1.0
Position 2 → 0.5
Position 3 → 0.33
Not found → 0.0
"""

from typing import Dict, List, Any
from app.ground_truth.metrics.common import find_answer_position


def calculate_mrr(
    expected_answer: str,
    retrieved_chunks: List[Dict[str, Any]],
    top_k: int = 3
) -> float:
    """
    Calculate MRR (Mean Reciprocal Rank) for a single query.

    MRR: 1/position of correct answer, or 0 if not found.

    Example:
        - Answer at position 1 → MRR = 1.0
        - Answer at position 2 → MRR = 0.5
        - Answer at position 3 → MRR = 0.333
        - Answer not found → MRR = 0.0

    Args:
        expected_answer: The ground truth answer
        retrieved_chunks: List of retrieved chunks with "content" key
        top_k: Number of top results to consider (default: 3)

    Returns:
        Reciprocal rank value (0.0 to 1.0)

    Interpretation:
        - Measures ranking quality of correct answer
        - Target: > 0.8 (usually in top 1-2 positions)
        - Higher is better
        - More nuanced than Hit Rate (penalizes lower positions)
    """
    position = find_answer_position(expected_answer, retrieved_chunks, top_k)
    if position == 0:
        return 0.0
    return 1.0 / position


def aggregate_mrr(mrr_values: List[float]) -> float:
    """
    Calculate mean MRR across multiple queries.

    Args:
        mrr_values: List of individual MRR values

    Returns:
        Average MRR (0.0 to 1.0)
    """
    if not mrr_values:
        return 0.0
    return sum(mrr_values) / len(mrr_values)
