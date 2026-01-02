from typing import List, Dict, Any, Union
from app.nodes.retrieval.metrics.base import BaseMetric

def check_answer_in_chunk(expected_answer: Union[str, List[str]], chunk: str) -> bool:
    if isinstance(expected_answer, str):
        return expected_answer.lower() in chunk.lower()
    return any(ea.lower() in chunk.lower() for ea in expected_answer)

def find_answer_position(expected_answer: Union[str, List[str]], retrieved_chunks: List[Dict[str, Any]], top_k: int) -> int:
    for position, chunk_data in enumerate(retrieved_chunks[:top_k], start=1):
        if check_answer_in_chunk(expected_answer, chunk_data["content"]):
            return position
    return 0

class HitRate(BaseMetric):
    def calculate(self, expected: str, actual: List[Dict[str, Any]], top_k: int = 3) -> float:
        # actual is list of retrieved chunks
        position = find_answer_position(expected, actual, top_k)
        return 1.0 if position > 0 else 0.0
        
    def aggregate(self, scores: List[float]) -> float:
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
