from sentence_transformers import CrossEncoder
from typing import List, Tuple
import numpy as np

import asyncio

class Reranker:
    def __init__(self, model_name: str = "mixedbread-ai/mxbai-rerank-base-v1"):
        # This model is much faster (110M params) and very high quality.
        # It's better suited for CPU environments than large M3/Gemma models.
        self.model = CrossEncoder(model_name)

    async def rank_async(self, query: str, documents: List[str]) -> List[Tuple[float, str]]:
        """
        Rerank documents asynchronously using a thread pool to avoid blocking the event loop.
        """
        if not documents:
            return []
        
        # Run the heavy computation in a thread pool
        return await asyncio.to_thread(self.rank, query, documents)

    def rank(self, query: str, documents: List[str]) -> List[Tuple[float, str]]:
        """
        Rerank documents based on the query (Synchronous).
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
