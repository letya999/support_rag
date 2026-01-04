from typing import List, Dict, Any
from app.nodes.retrieval.metrics.base import RetrievalBaseMetric

class AverageScore(RetrievalBaseMetric):
    """
    Metric to calculate the average score across retrieved chunks.
    """
    def calculate(self, expected: Any, actual: List[Dict[str, Any]], top_k: int = 3) -> float:
        # actual is list of chunks with scores: [{"content": "...", "score": 0.5}, ...]
        scores = [chunk.get("score", 0.0) for chunk in actual[:top_k]]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
