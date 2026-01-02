from typing import List, Dict, Any
from app.integrations.embeddings import get_embedding
from app.storage.vector_store import search_documents
from app.nodes.retrieval.models import RetrievalOutput

async def retrieve_context(question: str, top_k: int = 3) -> RetrievalOutput:
    """
    Logic for retrieval: embedding + vector search.
    """
    # Generate embedding
    embedding = await get_embedding(question)
    
    # Search in vector store
    results = await search_documents(embedding, top_k=top_k)
    
    # Extract content
    docs = [r.content for r in results]
    
    # Extract top result info
    top_result = results[0] if results else None
    confidence = top_result.score if top_result else 0.0
    best_doc_metadata = top_result.metadata if top_result else {}
    
    return RetrievalOutput(
        docs=docs,
        confidence=confidence,
        best_doc_metadata=best_doc_metadata
    )
