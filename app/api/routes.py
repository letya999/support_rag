from fastapi import APIRouter, Query, HTTPException, Depends
from urllib.parse import unquote
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.config.settings import settings
from app.storage.connection import get_sync_db_connection
from app.observability.tracing import observe
from app.observability.langfuse_client import get_langfuse_client
from app.observability.callbacks import get_langfuse_callback_handler
from app.pipeline.graph import rag_graph
from app.nodes.retrieval.search import retrieve_context

router = APIRouter()


# Telegram Bot Models
class RAGRequestBody(BaseModel):
    """Request model for RAG pipeline from Telegram bot"""
    question: str
    conversation_history: List[dict]
    user_id: str
    session_id: str


class RAGResponseBody(BaseModel):
    """Response model for RAG pipeline to Telegram bot"""
    answer: str
    sources: List[Dict[str, Any]] = []
    confidence: float = 0.0
    query_id: str = ""
    metadata: Optional[Dict[str, Any]] = None

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
    q = unquote(q)
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
    q = unquote(q)
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    langfuse_handler = get_langfuse_callback_handler()
    
    try:
        try:
            result = await rag_graph.ainvoke(
                {
                    "question": q,
                    "hybrid_used": hybrid,
                    "confidence_threshold": float("-inf") # Ignore confidence threshold as requested
                },
                config={
                    "callbacks": [langfuse_handler],
                    "run_name": "rag_pipeline"
                }
            )
        except Exception as e:
            # Check if it's likely a network/tracing timeout and retry without callbacks 
            if "timeout" in str(e).lower() or "connection" in str(e).lower():
                print(f"Warning: Tracing failed ({e}), retrying without callbacks.")
                result = await rag_graph.ainvoke(
                    {
                        "question": q,
                        "hybrid_used": hybrid,
                        "confidence_threshold": float("-inf") 
                    },
                    config={
                        "callbacks": [], 
                        "run_name": "rag_pipeline_retry"
                    }
                )
            else:
                raise e
        
        return {
            "answer": result.get("answer")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/query")
@observe()
async def rag_query(request: RAGRequestBody):
    """
    RAG query endpoint for Telegram bot.

    Accepts a question with conversation history context and returns an answer
    with sources and confidence score.

    Args:
        request: RAGRequestBody with question, conversation_history, user_id, session_id

    Returns:
        RAGResponseBody with answer, sources, confidence, and query_id
    """
    question = request.question
    conversation_history = request.conversation_history
    user_id = request.user_id
    session_id = request.session_id

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    langfuse_handler = get_langfuse_callback_handler()

    try:
        try:
            # Prepare state for RAG graph with conversation context
            input_state = {
                "question": question,
                "conversation_context": conversation_history,
                "user_id": user_id,
                "session_id": session_id,
                "hybrid_used": True,
                "confidence_threshold": float("-inf")  # Don't filter by confidence
            }

            # Run RAG graph
            result = await rag_graph.ainvoke(
                input_state,
                config={
                    "callbacks": [langfuse_handler],
                    "run_name": "telegram_rag_query"
                }
            )
        except Exception as e:
            # Retry without callbacks if there's a connection issue
            if "timeout" in str(e).lower() or "connection" in str(e).lower():
                print(f"Warning: Tracing failed ({e}), retrying without callbacks.")
                input_state = {
                    "question": question,
                    "conversation_context": conversation_history,
                    "user_id": user_id,
                    "session_id": session_id,
                    "hybrid_used": True,
                    "confidence_threshold": float("-inf")
                }
                result = await rag_graph.ainvoke(
                    input_state,
                    config={
                        "callbacks": [],
                        "run_name": "telegram_rag_query_retry"
                    }
                )
            else:
                raise e

        # Format response for Telegram bot
        answer = result.get("answer", "Не смог найти ответ.")
        sources = result.get("best_doc_metadata", [])
        confidence = result.get("confidence", 0.0)
        query_id = result.get("query_id", session_id)

        # Ensure sources is a list
        if isinstance(sources, dict):
            sources = [sources] if sources else []
        elif not isinstance(sources, list):
            sources = []

        return RAGResponseBody(
            answer=answer,
            sources=sources,
            confidence=float(confidence) if confidence else 0.0,
            query_id=str(query_id),
            metadata=result.get("metadata")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
