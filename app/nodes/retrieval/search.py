import asyncio
from typing import List, Dict, Any, Optional
from app.integrations.embeddings import get_embedding
from app.storage.vector_operations import vector_search as search_documents
from app.nodes.retrieval.models import RetrievalOutput
from app.nodes.query_expansion.expander import QueryExpander
from app.nodes.reranking.ranker import get_reranker
from app.nodes.hybrid_search.node import search_hybrid

async def retrieve_context(question: str, top_k: int = 3, category_filter: Optional[str] = None) -> RetrievalOutput:
    """
    SIMPLE retrieval: embedding + vector search for a single query.
    """
    embedding = await get_embedding(question)
    results = await search_documents(embedding, top_k=top_k, category_filter=category_filter)
    
    docs = [r.content for r in results]
    scores = [r.score for r in results]
    
    top_result = results[0] if results else None
    confidence = top_result.score if top_result else 0.0
    best_doc_metadata = top_result.metadata if top_result else {}
    
    return RetrievalOutput(
        docs=docs,
        scores=scores,
        confidence=confidence,
        best_doc_metadata=best_doc_metadata,
        vector_results=results
    )

async def retrieve_context_expanded(
    question: str, 
    top_k_retrieval: int = 10, 
    top_k_rerank: Optional[int] = None,
    use_expansion: bool = True,
    use_hybrid: bool = False,
    confidence_threshold: float = 0.5,
    category_filter: Optional[str] = None
) -> RetrievalOutput:
    """
    ADVANCED retrieval: optional expansion + parallel search + optional reranking.
    Includes a short-circuit logic: if initial search is confident, skip expensive steps.
    """
    # 1. Probe Search (Simple)
    # Check if the original question already yields high-confidence results
    initial_k = top_k_rerank if top_k_rerank else top_k_retrieval
    initial_output = await retrieve_context(question, top_k=initial_k, category_filter=category_filter)
    
    if initial_output.confidence >= confidence_threshold:
        # High confidence in initial results - skip expansion and reranking to save latency/cost
        return initial_output

    # 2. Expansion
    queries = [question]
    if use_expansion:
        expander = QueryExpander()
        queries = await expander.expand(question)
        
    # 3. Parallel Search
    if use_hybrid:
        tasks = [search_hybrid(q, top_k_retrieval) for q in queries]
    else:
        tasks = [search_single_query(q, top_k_retrieval, category_filter) for q in queries]
    all_results = await asyncio.gather(*tasks)
    
    # 4. Flatten and Deduplicate
    seen_contents = set()
    unique_results = []
    for results in all_results:
        for r in results:
            if r.content not in seen_contents:
                seen_contents.add(r.content)
                unique_results.append(r)
    
    # Sort by vector score
    unique_results = sorted(unique_results, key=lambda x: x.score, reverse=True)
    
    # 5. Optional Reranking
    if top_k_rerank is not None:
        docs_to_rerank = [r.content for r in unique_results]
        ranker = get_reranker()
        # Use async ranking to avoid blocking the event loop
        ranked_results = await ranker.rank_async(question, docs_to_rerank)
        
        # Take top K after rerank
        final_results = ranked_results[:top_k_rerank]
        docs = [doc for score, doc in final_results]
        scores = [score for score, doc in final_results]
        confidence = scores[0] if scores else 0.0
        # Find metadata for the best reranked doc
        best_doc_content = docs[0] if docs else None
        best_doc_metadata = next((r.metadata for r in unique_results if r.content == best_doc_content), {})
    else:
        # Just use vector results
        final_results = unique_results[:top_k_retrieval]
        docs = [r.content for r in final_results]
        scores = [r.score for r in final_results]
        confidence = scores[0] if scores else 0.0
        best_doc_metadata = final_results[0].metadata if final_results else {}

    return RetrievalOutput(
        docs=docs,
        scores=scores,
        confidence=confidence,
        best_doc_metadata=best_doc_metadata,
        vector_results=unique_results[:top_k_retrieval]
    )

async def search_single_query(query: str, top_k: int, category_filter: Optional[str] = None):
    embedding = await get_embedding(query)
    return await search_documents(embedding, top_k=top_k, category_filter=category_filter)
