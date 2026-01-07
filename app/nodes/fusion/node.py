from typing import List, Dict, Any
from app.nodes.base_node import BaseNode
from app.storage.models import SearchResult
from app.observability.tracing import observe

class FusionNode(BaseNode):
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fusion logic.

        Contracts:
            - Required Inputs: `vector_results` (List[SearchResult]), `lexical_results` (List[SearchResult])
            - Guaranteed Outputs: `docs` (List[str]), `rerank_scores` (List[float]), `confidence` (float), `best_doc_metadata` (dict)
        """
        vector_results = state.get("vector_results", [])
        lexical_results = state.get("lexical_results", [])
        
        fused_results = reciprocal_rank_fusion(
            vector_results=vector_results,
            lexical_results=lexical_results
        )
        
        docs = [r.content for r in fused_results]
        scores = [r.score for r in fused_results]
        
        return {
            "docs": docs,
            "rerank_scores": scores, # Using rerank_scores or just scores? 
            "confidence": scores[0] if scores else 0.0,
            "best_doc_metadata": fused_results[0].metadata if fused_results else {}
        }

def reciprocal_rank_fusion(
    vector_results: List[SearchResult],
    lexical_results: List[SearchResult],
    k: int = 60,
    top_n: int = 10
) -> List[SearchResult]:
    """
    Combine vector and lexical search results using Reciprocal Rank Fusion.
    """
    scores: Dict[str, float] = {}
    content_to_result: Dict[str, SearchResult] = {}
    
    # Process vector results
    for rank, result in enumerate(vector_results, 1):
        if result.content not in scores:
            scores[result.content] = 0.0
            content_to_result[result.content] = result
        scores[result.content] += 1.0 / (k + rank)
        
    # Process lexical results
    for rank, result in enumerate(lexical_results, 1):
        if result.content not in scores:
            scores[result.content] = 0.0
            content_to_result[result.content] = result
        scores[result.content] += 1.0 / (k + rank)
        
    # Sort by fused score
    sorted_content = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    fused_results = []
    for content, score in sorted_content[:top_n]:
        # Create a new SearchResult with the fused score
        original_result = content_to_result[content]
        fused_results.append(SearchResult(
            content=original_result.content,
            score=score,
            metadata=original_result.metadata
        ))
        
    return fused_results

# For backward compatibility
fusion_node = FusionNode()
