from typing import Dict, Any, List
from app.nodes.base_node import BaseNode
from app.nodes.reranking.ranker import get_reranker
from app.observability.tracing import observe

class RerankingNode(BaseNode):
    """
    Reranks retrieved documents for better relevance ordering.
    
    Contracts:
        Input:
            Required:
                - question (str): User question for scoring
                - docs (List[str]): Documents to rerank
            Optional: None
        
        Output:
            Guaranteed:
                - docs (List[str]): Reordered documents
                - rerank_scores (List[float]): New scores
            Conditional:
                - best_rerank_score (float): Top score
                - confidence (float): Confidence from best score
    """
    
    INPUT_CONTRACT = {
        "required": ["question", "docs"],
        "optional": []
    }
    
    OUTPUT_CONTRACT = {
        "guaranteed": ["docs", "rerank_scores"],
        "conditional": ["best_rerank_score", "confidence"]
    }
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reranking logic.

        Contracts:
            - Required Inputs: `question` (str), `docs` (List[str])
            - Optional Inputs: None
            - Guaranteed Outputs: `docs` (List[str], reordered), `rerank_scores` (List[float]), `best_rerank_score` (float), `confidence` (float)
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
