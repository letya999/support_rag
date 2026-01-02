from typing import List, Dict, Any, Union
from app.nodes.retrieval.metrics.base import BaseMetric

class F1Score(BaseMetric):
    def calculate(self, expected: Union[str, List[str]], actual: List[Dict[str, Any]], top_k: int = 10) -> float:
        """
        Calculate F1 Score: harmonic mean of Precision@K and Recall@K.
        """
        if isinstance(expected, str):
            expected = [expected]
            
        if not expected:
            return 0.0
            
        if not actual:
            return 0.0
            
        retrieved_contents = [r["content"].lower() for r in actual[:top_k]]
        
        relevant_count = 0
        for exp in expected:
            if any(exp.lower() in ret for ret in retrieved_contents):
                relevant_count += 1
                
        recall = relevant_count / len(expected)
        # Precision is based on how many of the TOP K were actually relevant
        precision = relevant_count / min(len(actual), top_k)
        
        if (precision + recall) == 0:
            return 0.0
            
        return 2 * (precision * recall) / (precision + recall)
        
    def aggregate(self, scores: List[float]) -> float:
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
