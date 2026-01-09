from fastapi import APIRouter, Query, HTTPException, Header, Request
from urllib.parse import unquote
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.settings import settings
from app.observability.tracing import observe
from app.observability.filtered_handler import FilteredLangfuseHandler
from app.pipeline.graph import rag_graph
from app.services.config_loader.loader import load_shared_config
from app.services.identity.manager import IdentityManager
from app.services.identity.request_extractor import RequestMetadataExtractor

router = APIRouter()

# Default confidence threshold
DEFAULT_CONFIDENCE_THRESHOLD = 0.3

# Telegram Bot Models
class RAGRequestBody(BaseModel):
    """Request model for RAG pipeline from Telegram bot"""
    question: str
    conversation_history: List[dict]
    user_id: str
    session_id: str
    user_metadata: Optional[Dict[str, Any]] = {}


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
    request: Request,
    q: str = Query(..., description="Question to answer"),
    hybrid: bool = Query(True, description="Enable hybrid search (Vector + Lexical)"),
    x_device_fingerprint: Optional[str] = Header(None),
    x_device_metadata: Optional[str] = Header(None)
):
    q = unquote(q)
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # 1. Extract Technical Metadata
    technical_metadata = RequestMetadataExtractor.extract(request)

    # 2. Prepare Payload
    client_payload = {}
    if x_device_metadata:
        try:
             import json
             client_payload = json.loads(unquote(x_device_metadata))
        except:
             pass
    
    # Merge technical info
    final_payload = {**client_payload, **technical_metadata}
    
    # 3. Resolve Identity
    user_id = await IdentityManager.resolve_identity(
        channel="device_fingerprint",
        identifier=x_device_fingerprint,
        metadata_payload=final_payload
    )

    langfuse_handler = FilteredLangfuseHandler()
    global_config = load_shared_config("global")
    confidence_threshold = global_config.get("parameters", {}).get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
    
    try:
        try:
            result = await rag_graph.ainvoke(
                {
                    "question": q,
                    "hybrid_used": hybrid,
                    "confidence_threshold": confidence_threshold,
                    "user_id": user_id 
                },
                config={
                    "callbacks": [langfuse_handler],
                    "run_name": "rag_pipeline"
                }
            )
        except Exception as e:
            if "timeout" in str(e).lower() or "connection" in str(e).lower():
                print(f"Warning: Tracing failed ({e}), retrying without callbacks.")
                result = await rag_graph.ainvoke(
                    {
                        "question": q,
                        "hybrid_used": hybrid,
                        "confidence_threshold": confidence_threshold,
                         "user_id": user_id
                    },
                    config={"callbacks": [], "run_name": "rag_pipeline_retry"}
                )
            else:
                raise e
        
        return {"answer": result.get("answer")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/query")
@observe()
async def rag_query(
    request: Request,
    body: RAGRequestBody
):
    """RAG query endpoint for Telegram bot."""
    question = body.question
    conversation_history = body.conversation_history
    request_user_id = body.user_id
    session_id = body.session_id
    
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # 1. Extract Technical Metadata
    technical_metadata = RequestMetadataExtractor.extract(request)

    # 2. Merge with Body Metadata
    user_metadata = body.user_metadata or {}
    user_metadata.update(technical_metadata)

    # 3. Resolve Identity
    internal_user_id = await IdentityManager.resolve_identity(
        channel="telegram",
        identifier=request_user_id,
        metadata_payload=user_metadata
    )

    langfuse_handler = FilteredLangfuseHandler()
    global_config = load_shared_config("global")
    confidence_threshold = global_config.get("parameters", {}).get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)

    try:
        try:
            input_state = {
                "question": question,
                "conversation_context": conversation_history,
                "user_id": internal_user_id,
                "session_id": session_id,
                "hybrid_used": True,
                "confidence_threshold": confidence_threshold
            }
            result = await rag_graph.ainvoke(
                input_state,
                config={"callbacks": [langfuse_handler], "run_name": "telegram_rag_query"}
            )
        except Exception as e:
            if "timeout" in str(e).lower() or "connection" in str(e).lower():
                print(f"Warning: Tracing failed ({e}), retrying without callbacks.")
                input_state = {
                    "question": question,
                    "conversation_context": conversation_history,
                    "user_id": internal_user_id,
                    "session_id": session_id,
                    "hybrid_used": True,
                    "confidence_threshold": confidence_threshold
                }
                result = await rag_graph.ainvoke(
                    input_state,
                    config={"callbacks": [], "run_name": "telegram_rag_query_retry"}
                )
            else:
                raise e

        answer = result.get("answer") or result.get("escalation_message") or "Не смог найти ответ."
        sources = result.get("best_doc_metadata", [])
        confidence = result.get("confidence", 0.0)
        query_id = result.get("query_id", session_id)

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
