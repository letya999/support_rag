"""Ground Truth Metrics

Individual metric functions for retrieval evaluation:
- Hit Rate (Recall@K): % of queries where correct answer in top-K
- MRR (Mean Reciprocal Rank): Average reciprocal position of correct answer
- Exact Match: % of queries where top-1 is correct

Usage:
    from app.ground_truth.metrics import calculate_hit_rate, calculate_mrr, calculate_exact_match

    metrics = {
        "hit_rate": calculate_hit_rate(expected_answer, chunks, top_k=3),
        "mrr": calculate_mrr(expected_answer, chunks, top_k=3),
        "exact_match": calculate_exact_match(expected_answer, chunks),
    }
"""

from app.ground_truth.metrics.hit_rate import (
    calculate_hit_rate,
    aggregate_hit_rates,
)
from app.ground_truth.metrics.mrr import (
    calculate_mrr,
    aggregate_mrr,
)
from app.ground_truth.metrics.exact_match import (
    calculate_exact_match,
    aggregate_exact_matches,
)
from app.ground_truth.metrics.common import (
    check_answer_in_chunk,
    find_answer_position,
)

__all__ = [
    # Hit Rate
    "calculate_hit_rate",
    "aggregate_hit_rates",
    # MRR
    "calculate_mrr",
    "aggregate_mrr",
    # Exact Match
    "calculate_exact_match",
    "aggregate_exact_matches",
    # Common utilities
    "check_answer_in_chunk",
    "find_answer_position",
]


def calculate_all_metrics(
    expected_answer: str,
    retrieved_chunks: list,
    top_k: int = 3
) -> dict:
    """
    Calculate all metrics for a single query.

    Args:
        expected_answer: The ground truth answer
        retrieved_chunks: List of retrieved chunks with "content" key
        top_k: Number of top results to consider

    Returns:
        {
            "hit_rate": 0 or 1,
            "mrr": float,
            "exact_match": 0 or 1
        }
    """
    return {
        "hit_rate": calculate_hit_rate(expected_answer, retrieved_chunks, top_k),
        "mrr": calculate_mrr(expected_answer, retrieved_chunks, top_k),
        "exact_match": calculate_exact_match(expected_answer, retrieved_chunks),
    }
