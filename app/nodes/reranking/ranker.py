from sentence_transformers import CrossEncoder
from typing import List, Tuple
import numpy as np

class Reranker:
    def __init__(self, model_name: str = "cross-encoder/qnli-distilroberta-base"):
        self.model = CrossEncoder(model_name)

    def rank(self, query: str, documents: List[str]) -> List[Tuple[float, str]]:
        """
        Rerank documents based on the query.
        Returns a list of (score, document) tuples sorted by score descending.
        """
        if not documents:
            return []
            
        pairs = [[query, doc] for doc in documents]
        scores = self.model.predict(pairs)
        
        # Convert to float and combine with docs
        results = zip(scores.tolist(), documents)
        
        # Sort by score descending
        sorted_results = sorted(results, key=lambda x: x[0], reverse=True)
        
        return sorted_results

# Singleton instance
reranker_instance = None

def get_reranker():
    global reranker_instance
    if reranker_instance is None:
        reranker_instance = Reranker()
    return reranker_instance
