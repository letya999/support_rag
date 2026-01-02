"""Ground Truth Matching Module

Evaluates retrieval performance using ground truth dataset with metrics:
- Hit Rate (Recall@K)
- MRR (Mean Reciprocal Rank)
- Exact Match (top-1)

Usage in LangGraph:
    from app.ground_truth.evaluator import evaluate_ground_truth

    # Can be used as a node or after any retrieval node
    results = await evaluate_ground_truth(langfuse_client, top_k=3)
"""

from app.ground_truth.evaluator import evaluate_ground_truth
from app.ground_truth.dataset_sync import (
    load_ground_truth_dataset,
    sync_dataset_to_langfuse,
    get_dataset_from_langfuse,
    DATASET_NAME,
)
from app.ground_truth.metrics import (
    calculate_hit_rate,
    aggregate_hit_rates,
    calculate_mrr,
    aggregate_mrr,
    calculate_exact_match,
    aggregate_exact_matches,
    calculate_all_metrics,
    check_answer_in_chunk,
    find_answer_position,
)

__all__ = [
    "evaluate_ground_truth",
    "load_ground_truth_dataset",
    "sync_dataset_to_langfuse",
    "get_dataset_from_langfuse",
    "DATASET_NAME",
    # Metrics - individual
    "calculate_hit_rate",
    "aggregate_hit_rates",
    "calculate_mrr",
    "aggregate_mrr",
    "calculate_exact_match",
    "aggregate_exact_matches",
    # Metrics - utilities
    "calculate_all_metrics",
    "check_answer_in_chunk",
    "find_answer_position",
]
