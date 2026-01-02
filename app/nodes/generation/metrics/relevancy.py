from app.nodes.retrieval.metrics.base import BaseMetric
from typing import Any, List

class Relevancy(BaseMetric):
    def calculate(self, expected: Any, actual: Any, **kwargs) -> float:
        # TODO: Implement LLM-based relevancy
        return 0.0
        
    def aggregate(self, scores: List[float]) -> float:
        return 0.0
