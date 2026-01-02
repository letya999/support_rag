from typing import List, Dict, Any, Union
import math
from app.nodes.retrieval.metrics.base import BaseMetric

class NDCG(BaseMetric):
    def calculate(self, expected: Union[str, List[str]], actual: List[Dict[str, Any]], top_k: int = 10) -> float:
        """
        Calculate NDCG@K (Normalized Discounted Cumulative Gain).
        For this simplified version, we assume binary relevance: 1 if chunk contains answer, 0 otherwise.
        """
        if isinstance(expected, str):
            expected = [expected]
            
        retrieved_contents = [r["content"].lower() for r in actual[:top_k]]
        
        dcg = 0.0
        idcg = 0.0
        
        # Calculate DCG
        relevant_items_count = 0
        for i, content in enumerate(retrieved_contents):
            # Check relevance
            is_relevant = any(exp.lower() in content for exp in expected)
            if is_relevant:
                rel = 1.0 # Binary relevance
                dcg += rel / math.log2(i + 2) # i starts at 0, so i+2 is 2, 3...
                relevant_items_count += 1
                
        # Calculate IDCG (Ideal DCG)
        # In ideal ranking, all relevant items are at the top
        # We have 'relevant_items_count' actually found relevant items? 
        # No, IDCG should be based on the total possible relevant items present in the dataset (or capped at K)
        # But here we only know about 'expected' count.
        # Assuming each expected chunk is distinct and should appear once.
        # Maximum possible relevant items is min(len(expected), top_k)
        
        ideal_relevant_count = min(len(expected), top_k)
        
        for i in range(ideal_relevant_count):
            rel = 1.0
            idcg += rel / math.log2(i + 2)
            
        if idcg == 0:
            return 0.0
            
        return dcg / idcg

    def aggregate(self, scores: List[float]) -> float:
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
