from typing import Dict, Any, List
from app.nodes.base_node import BaseNode
from app.nodes.reranking.ranker import get_reranker
from app.observability.tracing import observe

class RerankingNode(BaseNode):
    @observe(as_type="span")
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reranking logic.
        """
        question = state.get("question", "")
        docs = state.get("docs", [])
        
        if not docs:
            return {"docs": [], "rerank_scores": []}
        
        ranker = get_reranker()
        ranked_results = await ranker.rank_async(question, docs)
        
        # Unpack scores and docs
        reranked_scores = [score for score, doc in ranked_results]
        reranked_docs = [doc for score, doc in ranked_results]
        
        return {
            "docs": reranked_docs,
            "rerank_scores": reranked_scores,
            "best_rerank_score": reranked_scores[0] if reranked_scores else 0.0,
            "confidence": reranked_scores[0] if reranked_scores else 0.0
        }

# For backward compatibility
rerank_node = RerankingNode()
