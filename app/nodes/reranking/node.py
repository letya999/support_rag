from typing import Dict, Any, List
from app.nodes.reranking.ranker import get_reranker
from app.observability.tracing import observe

@observe(as_type="span")
async def rerank_node(state: Dict[str, Any]):
    """
    LangGraph node for reranking retrieved documents.
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
    
    # Update langfuse trace with scores
    # Langfuse observe decorator allows adding attributes via the context if available,
    # or it might automatically log inputs/outputs.
    
    return {
        "docs": reranked_docs,
        "rerank_scores": reranked_scores,
        "best_rerank_score": reranked_scores[0] if reranked_scores else 0.0,
        "confidence": reranked_scores[0] if reranked_scores else 0.0
    }
