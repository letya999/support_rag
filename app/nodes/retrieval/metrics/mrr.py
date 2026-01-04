from typing import List, Dict, Any
from app.nodes.retrieval.metrics.base import RetrievalBaseMetric
from app.nodes.retrieval.metrics.hit_rate import find_answer_position

class MRR(RetrievalBaseMetric):
    def calculate(self, expected: str, actual: List[Dict[str, Any]], top_k: int = 3) -> float:
        position = find_answer_position(expected, actual, top_k)
        if position == 0:
            return 0.0
        return 1.0 / position
