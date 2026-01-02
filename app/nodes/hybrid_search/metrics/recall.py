from typing import List, Dict, Any, Union
from app.nodes.retrieval.metrics.base import BaseMetric

class Recall(BaseMetric):
    def calculate(self, expected: Union[str, List[str]], actual: List[Dict[str, Any]], top_k: int = 10) -> float:
        """
        Calculate Recall@K: proportion of expected chunks found in top K results.
        """
        if isinstance(expected, str):
            expected = [expected]
        
        if not expected:
            return 1.0 # Or 0.0 depending on convention, but usually 1.0 if nothing expected
            
        retrieved_contents = [r["content"].lower() for r in actual[:top_k]]
        
        relevant_count = 0
        for exp in expected:
            # Check if this expected chunk is present in ANY of the retrieved chunks
            if any(exp.lower() in ret for ret in retrieved_contents):
                relevant_count += 1
                
        return relevant_count / len(expected)
        
    def aggregate(self, scores: List[float]) -> float:
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
