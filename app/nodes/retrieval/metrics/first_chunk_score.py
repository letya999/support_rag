from typing import List, Dict, Any
from app.nodes.retrieval.metrics.base import BaseMetric

class FirstChunkScore(BaseMetric):
    """
    Metric to return the score of the very first retrieved chunk.
    """
    def calculate(self, expected: Any, actual: List[Dict[str, Any]], top_k: int = 3) -> float:
        # actual is list of chunks with scores: [{"content": "...", "score": 0.5}, ...]
        if not actual:
            return 0.0
        return float(actual[0].get("score", 0.0))
        
    def aggregate(self, scores: List[float]) -> float:
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
