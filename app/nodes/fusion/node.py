from typing import List, Dict
from app.storage.models import SearchResult

def reciprocal_rank_fusion(
    vector_results: List[SearchResult],
    lexical_results: List[SearchResult],
    k: int = 60,
    top_n: int = 10
) -> List[SearchResult]:
    """
    Combine vector and lexical search results using Reciprocal Rank Fusion.
    
    Args:
        vector_results: Results from vector search
        lexical_results: Results from lexical search
        k: Constant for RRF formula (default 60)
        top_n: Number of top results to return
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
