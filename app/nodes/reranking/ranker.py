from sentence_transformers import CrossEncoder
from typing import List, Tuple
import numpy as np

import asyncio
from app.services.config_loader.loader import get_node_params

class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        # This model is state-of-the-art for multilingual reranking.
        # It handles RU/EN cross-lingual pairs very well.
        self.model = CrossEncoder(model_name)

    async def rank_async(self, query: str, documents: List[str]) -> List[Tuple[float, str]]:
        """
        Rerank documents asynchronously using a thread pool to avoid blocking the event loop.
        """
        if not documents:
            return []
        
        # Run the heavy computation in a thread pool
        return await asyncio.to_thread(self.rank, query, documents)

    def _extract_answer(self, doc: str) -> str:
        """Extract only the answer from the document."""
        if "Answer:" in doc:
            return doc.split("Answer:", 1)[1].strip()
        return doc

    def _prepare_pairs(self, query: str, docs: List[str]) -> List[List[str]]:
        """Prepare pairs for reranker in the correct format."""
        pairs = []
        for doc in docs:
            # Clean formatting
            clean_doc = self._extract_answer(doc)
            pairs.append([query, clean_doc])
        return pairs

    def rank(self, query: str, documents: List[str]) -> List[Tuple[float, str]]:
        """
        Rerank documents based on the query (Synchronous).
        """
        if not documents:
            return []
            
        pairs = self._prepare_pairs(query, documents)
        
        # Predict returns logits for this model
        scores = self.model.predict(pairs)
        
        # Apply sigmoid to get [0, 1] range
        scores = 1 / (1 + np.exp(-scores))
        
        # Convert to float and combine with original docs (not cleaned ones)
        results = zip(scores.tolist(), documents)
        
        # Sort by score descending
        sorted_results = sorted(results, key=lambda x: x[0], reverse=True)
        
        return sorted_results



# Singleton instance
reranker_instance = None

def get_reranker():
    global reranker_instance
    if reranker_instance is None:
        params = get_node_params("reranking")
        model_name = params.get("model_name", "BAAI/bge-reranker-v2-m3")
        reranker_instance = Reranker(model_name=model_name)
    return reranker_instance
