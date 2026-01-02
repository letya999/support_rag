from typing import List, Dict, Any
from app.nodes.retrieval.metrics.base import BaseMetric
from app.nodes.retrieval.metrics.hit_rate import check_answer_in_chunk

class ExactMatch(BaseMetric):
    def calculate(self, expected: str, actual: List[Dict[str, Any]], **kwargs) -> float:
        if not actual:
            return 0.0
        top_chunk = actual[0]["content"]
        return 1.0 if check_answer_in_chunk(expected, top_chunk) else 0.0
        
    def aggregate(self, scores: List[float]) -> float:
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
