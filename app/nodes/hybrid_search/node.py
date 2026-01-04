import asyncio
from typing import List, Dict, Any
from langfuse import observe
from app.nodes.retrieval.storage import vector_search as search_documents
from app.nodes.lexical_search.node import lexical_search_node
from app.nodes.fusion.node import reciprocal_rank_fusion
from app.storage.models import SearchResult
from app.integrations.embeddings import get_embedding

@observe(as_type="span")
async def search_hybrid(query: str, top_k: int = 10) -> List[SearchResult]:
    """
    Perform hybrid search by combining vector and lexical search.
    Logic function independent of LangGraph state.
    """
    # 1. Get embedding for vector search
    embedding_task = get_embedding(query)
    embedding = await embedding_task
    
    # 2. Run both searches in parallel
    vector_task = search_documents(embedding, top_k=top_k * 2)
    lexical_task = lexical_search_node(query, top_k=top_k * 2)
    
    vector_results, lexical_results = await asyncio.gather(vector_task, lexical_task)
    
    # 3. Combine results using RRF (Fusion Node)
    fused_results = reciprocal_rank_fusion(
        vector_results=vector_results,
        lexical_results=lexical_results,
        top_n=top_k
    )
    
    return fused_results

@observe(as_type="span")
async def hybrid_search_node(state: Dict[str, Any]):
    """
    LangGraph node for hybrid search.
    Handles single or multiple queries from state.
    """
    question = state.get("aggregated_query") or state.get("question", "")
    queries = state.get("queries", [question])
    
    # If expansion happened, queries might be list.
    # We should run hybrid search for each query?
    # This matches behavior of `retrieve_context_expanded` but inside the node.
    
    top_k = 10 # Default or from config? Hard to pass config in simple Node.
    
    tasks = [search_hybrid(q, top_k=top_k) for q in queries]
    all_results_lists = await asyncio.gather(*tasks)
    
    # Deduplicate and Flatten
    seen_contents = set()
    unique_results = []
    
    for results in all_results_lists:
        for r in results:
            if r.content not in seen_contents:
                seen_contents.add(r.content)
                unique_results.append(r)
                
    # Sort by score (RRF score from hybrid)
    unique_results = sorted(unique_results, key=lambda x: x.score, reverse=True)
    
    docs = [r.content for r in unique_results]
    scores = [r.score for r in unique_results]
    
    return {
        "docs": docs,
        "scores": scores,
        "confidence": scores[0] if scores else 0.0,
        "best_doc_metadata": unique_results[0].metadata if unique_results else {}
    }
