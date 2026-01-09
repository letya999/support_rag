"""
Search service for API layer - abstracts retrieval nodes.
Unified interface for searching documents via Vector and Lexical search.
"""
from typing import List, Dict, Any
from app.integrations.embeddings import get_embedding
from app.storage.vector_operations import vector_search
from app.storage.lexical_operations import lexical_search_db

async def search_documents(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Vector search through storage layer (Unified Interface).
    
    Args:
        query: Search string
        top_k: Number of results
        
    Returns:
        List of dicts with content, score, and metadata
    """
    emb = await get_embedding(query)
    # Using the vector_search from storage layer directly
    results = await vector_search(emb, top_k)
    
    return [
        {
            "content": r.content,
            "score": r.score,
            "metadata": r.metadata
        }
        for r in results
    ]

async def search_lexical(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Lexical search through storage layer.
    """
    results = await lexical_search_db(query, top_k)
    
    return [
        {
            "content": r.content,
            "score": r.score,
            "metadata": r.metadata
        }
        for r in results
    ]
