"""Common utilities for metrics"""

from typing import Dict, List, Any


def check_answer_in_chunk(expected_answer: str, chunk: str) -> bool:
    """
    Check if expected answer is contained in the chunk.

    Args:
        expected_answer: The ground truth answer to look for
        chunk: The retrieved chunk content

    Returns:
        True if answer found (case-insensitive), False otherwise
    """
    chunk_lower = chunk.lower()
    answer_lower = expected_answer.lower()
    return answer_lower in chunk_lower


def find_answer_position(
    expected_answer: str,
    retrieved_chunks: List[Dict[str, Any]],
    top_k: int = 3
) -> int:
    """
    Find position (1-based) of correct answer in retrieved chunks.

    Args:
        expected_answer: The ground truth answer
        retrieved_chunks: List of retrieved chunks with "content" key
        top_k: Number of top results to search

    Returns:
        Position (1-based) if found, 0 if not found
    """
    for position, chunk_data in enumerate(retrieved_chunks[:top_k], start=1):
        chunk = chunk_data["content"]
        if check_answer_in_chunk(expected_answer, chunk):
            return position
    return 0
