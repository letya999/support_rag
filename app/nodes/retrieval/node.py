from typing import Dict, Any
from app.nodes.retrieval.search import retrieve_context
from app.observability.tracing import observe

@observe(as_type="span")
async def retrieve_node(state: Dict[str, Any]):
    """
    LangGraph node for simple retrieval.
    """
    question = state.get("question", "")
    category_filter = state.get("matched_category") if state.get("filter_used") else None
    output = await retrieve_context(question, category_filter=category_filter)
    
    return {
        "docs": output.docs,
        "scores": output.scores,
        "confidence": output.confidence,
        "best_doc_metadata": output.best_doc_metadata
    }

@observe(as_type="span")
async def retrieve_expanded_node(state: Dict[str, Any]):
    """
    LangGraph node for expanded retrieval (multiple queries).
    """
    queries = state.get("queries", [state.get("question", "")])
    
    import asyncio
    from app.nodes.retrieval.search import search_single_query
    
    tasks = [search_single_query(q, top_k=10) for q in queries]
    all_results = await asyncio.gather(*tasks)
    
    seen_contents = set()
    unique_results = []
    for results in all_results:
        for r in results:
            if r.content not in seen_contents:
                seen_contents.add(r.content)
                unique_results.append(r)
    
    unique_results = sorted(unique_results, key=lambda x: x.score, reverse=True)
    
    docs = [r.content for r in unique_results]
    scores = [r.score for r in unique_results]
    
    return {
        "docs": docs,
        "scores": scores,
        "confidence": scores[0] if scores else 0.0,
        "best_doc_metadata": unique_results[0].metadata if unique_results else {}
    }
