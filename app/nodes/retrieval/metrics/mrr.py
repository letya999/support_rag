from typing import List, Dict, Any
from app.nodes.retrieval.metrics.base import BaseMetric
from app.nodes.retrieval.metrics.hit_rate import find_answer_position

class MRR(BaseMetric):
    def calculate(self, expected: str, actual: List[Dict[str, Any]], top_k: int = 3) -> float:
        position = find_answer_position(expected, actual, top_k)
        if position == 0:
            return 0.0
        return 1.0 / position
        
    def aggregate(self, scores: List[float]) -> float:
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
