import asyncio
from typing import List
from langfuse import observe
from app.nodes.retrieval.storage import vector_search as search_documents
from app.nodes.lexical_search.node import lexical_search_node
from app.nodes.fusion.node import reciprocal_rank_fusion
from app.storage.models import SearchResult
from app.integrations.embeddings import get_embedding

@observe(as_type="span")
async def hybrid_search_node(query: str, top_k: int = 10) -> List[SearchResult]:
    """
    Perform hybrid search by combining vector and lexical search.
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
