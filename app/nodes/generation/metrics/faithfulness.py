from app.nodes.retrieval.metrics.base import BaseMetric
from typing import Any, List

class Faithfulness(BaseMetric):
    def calculate(self, expected: Any, actual: Any, **kwargs) -> float:
        # TODO: Implement LLM-based faithfulness
        return 0.0
        
    def aggregate(self, scores: List[float]) -> float:
        return 0.0
