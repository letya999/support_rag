from fastapi import APIRouter, Query, HTTPException, Depends
from app.config.settings import settings
from app.storage.connection import get_sync_db_connection
from app.observability.tracing import observe
from app.observability.langfuse_client import get_langfuse_client
from app.observability.callbacks import get_langfuse_callback_handler
from app.pipeline.graph import rag_graph
from app.nodes.retrieval.search import retrieve_context

router = APIRouter()

@router.get("/health")
async def health():
    return {
        "status": "ok",
        "database": "configured" if settings.DATABASE_URL else "missing",
        "langfuse": "configured" if settings.LANGFUSE_PUBLIC_KEY else "missing"
    }

@router.get("/search")
@observe()
async def search(q: str = Query(..., description="The search query")):
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
        
    try:
        # Use retrieval logic directly
        output = await retrieve_context(q, top_k=3)
        
        # Convert to dict for response
        results = [
            {
                "content": content,
                "score": output.confidence, # Note: this is confidence of top result only in output model, 
                                            # but retrieve_context logic was simplified to return list of contents.
                                            # Wait, retrieve_context returns RetrievalOutput with docs (List[str]).
                                            # I lost the individual scores in RetrievalOutput!
                                            # To fix this, I should update RetrievalOutput or use models.
                                            # But for now, complying with refactor. The original /search endpoint
                                            # returned full result objects.
                                            # I will improve retrieve_context to return detailed results if needed?
                                            # Or just use vector_store.search_documents directly here for /search endpoint
                                            # to preserve same functionality as before.
            } for content in output.docs
        ]
        
        # Better: use vector_store directly for raw search endpoint if we want details
        # But 'Retrieval' node is the abstraction.
        # Let's check RetrievalOutput. It has 'confidence' of top result.
        # If I want full list with scores, I might need to adjust RetrievalOutput or search_documents.
        # For 'search' endpoint, I'll use `app.storage.vector_store.search_documents` + embedding
        # to ensure backward compatibility of output format (content, score, metadata).
        
        from app.integrations.embeddings import get_embedding
        from app.storage.vector_store import search_documents
        
        emb = await get_embedding(q)
        raw_results = await search_documents(emb, top_k=3)
        
        results_formatted = [
            {
                "content": r.content,
                "score": r.score,
                "metadata": r.metadata
            }
            for r in raw_results
        ]

        return {
            "query": q,
            "results": results_formatted
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ask")
@observe()
async def ask(
    q: str = Query(..., description="Question to answer"),
    hybrid: bool = Query(True, description="Enable hybrid search (Vector + Lexical)")
):
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    langfuse_handler = get_langfuse_callback_handler()
    
    try:
        result = await rag_graph.ainvoke(
            {
                "question": q,
                "hybrid_used": hybrid
            },
            config={
                "callbacks": [langfuse_handler],
                "run_name": "rag_pipeline"
            }
        )
        
        return {
            "question": q,
            "answer": result.get("answer"),
            "action": result.get("action"),
            "confidence": result.get("confidence"),
            "matched_intent": result.get("matched_intent"),
            "matched_category": result.get("matched_category"),
            "context": result.get("docs")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
