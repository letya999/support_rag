"""Ground Truth Matching Metrics"""

from typing import Dict, List, Any


def check_answer_in_chunk(expected_answer: str, chunk: str) -> bool:
    """Check if expected answer is contained in the chunk."""
    chunk_lower = chunk.lower()
    answer_lower = expected_answer.lower()
    return answer_lower in chunk_lower


def calculate_hit_rate(expected_answer: str, retrieved_chunks: List[Dict[str, Any]], top_k: int = 3) -> int:
    """
    Hit Rate (Recall@K): 1 if correct answer in top-K, 0 otherwise.

    Args:
        expected_answer: The ground truth answer
        retrieved_chunks: List of retrieved chunks with "content" key
        top_k: Number of top results to consider

    Returns:
        1 if found, 0 otherwise
    """
    for position, chunk_data in enumerate(retrieved_chunks[:top_k], start=1):
        chunk = chunk_data["content"]
        if check_answer_in_chunk(expected_answer, chunk):
            return 1
    return 0


def calculate_mrr(expected_answer: str, retrieved_chunks: List[Dict[str, Any]], top_k: int = 3) -> float:
    """
    MRR (Mean Reciprocal Rank): 1/position of correct answer.

    Position 1 → 1.0
    Position 2 → 0.5
    Position 3 → 0.33
    Not found → 0.0

    Args:
        expected_answer: The ground truth answer
        retrieved_chunks: List of retrieved chunks with "content" key
        top_k: Number of top results to consider

    Returns:
        Reciprocal rank value
    """
    for position, chunk_data in enumerate(retrieved_chunks[:top_k], start=1):
        chunk = chunk_data["content"]
        if check_answer_in_chunk(expected_answer, chunk):
            return 1.0 / position
    return 0.0


def calculate_exact_match(expected_answer: str, retrieved_chunks: List[Dict[str, Any]]) -> int:
    """
    Exact Match: 1 if top-1 result is correct, 0 otherwise.

    Args:
        expected_answer: The ground truth answer
        retrieved_chunks: List of retrieved chunks with "content" key

    Returns:
        1 if top-1 matches, 0 otherwise
    """
    if not retrieved_chunks:
        return 0

    top_chunk = retrieved_chunks[0]["content"]
    if check_answer_in_chunk(expected_answer, top_chunk):
        return 1
    return 0


def calculate_all_metrics(
    expected_answer: str,
    retrieved_chunks: List[Dict[str, Any]],
    top_k: int = 3
) -> Dict[str, float]:
    """
    Calculate all metrics for a single query.

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
