from fastapi import APIRouter, Query, HTTPException
from urllib.parse import unquote
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.settings import settings
from app.observability.tracing import observe
from app.observability.filtered_handler import FilteredLangfuseHandler
from app.pipeline.graph import rag_graph
from app.services.config_loader.loader import load_shared_config

router = APIRouter()

# Default confidence threshold (fallback if config fails to load)
DEFAULT_CONFIDENCE_THRESHOLD = 0.3

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
        # Use search service
        from app.services.search import search_documents
        
        results_formatted = await search_documents(q, top_k=3)

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
    
    # Use Filtered Langfuse Handler to reduce trace bloat
    langfuse_handler = FilteredLangfuseHandler()
    
    # Get global confidence threshold from pipeline config
    global_config = load_shared_config("global")
    confidence_threshold = global_config.get("parameters", {}).get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
    
    try:
        try:
            result = await rag_graph.ainvoke(
                {
                    "question": q,
                    "hybrid_used": hybrid,
                    "confidence_threshold": confidence_threshold
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
                        "confidence_threshold": confidence_threshold
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
    """
    question = request.question
    conversation_history = request.conversation_history
    user_id = request.user_id
    session_id = request.session_id

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Use Filtered Langfuse Handler to reduce trace bloat
    langfuse_handler = FilteredLangfuseHandler()

    # Get global confidence threshold from pipeline config
    global_config = load_shared_config("global")
    confidence_threshold = global_config.get("parameters", {}).get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)

    try:
        try:
            # Prepare state for RAG graph with conversation context
            input_state = {
                "question": question,
                "conversation_context": conversation_history,
                "user_id": user_id,
                "session_id": session_id,
                "hybrid_used": True,
                "confidence_threshold": confidence_threshold
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
                    "confidence_threshold": confidence_threshold
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
        answer = result.get("answer") or result.get("escalation_message") or "Не смог найти ответ."
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
