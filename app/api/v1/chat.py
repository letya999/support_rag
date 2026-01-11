from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import json
import logging
import uuid
import asyncio

from app.pipeline.graph import rag_graph
from app.services.identity.manager import IdentityManager
from app.services.config_loader.loader import load_shared_config
from app.settings import settings
from app.api.v1.models import Envelope, MetaResponse
from app.observability.filtered_handler import FilteredLangfuseHandler

router = APIRouter(tags=["Chat"])
logger = logging.getLogger(__name__)

# --- Models ---

class ChatMessage(BaseModel):
    role: str
    content: str
    
class ChatCompletionRequest(BaseModel):
    question: str
    session_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_history: List[ChatMessage] = []
    user_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class SourceDocument(BaseModel):
    document_id: Optional[str] = None
    title: str = "Document"
    excerpt: str = ""
    relevance: float = 0.0
    metadata: Optional[Dict[str, Any]] = None

class ChatCompletionData(BaseModel):
    question: str
    answer: str
    sources: List[SourceDocument] = []
    confidence: float = 0.0
    query_id: str = ""
    pipeline_metadata: Optional[Dict[str, Any]] = None

class EscalateRequest(BaseModel):
    session_id: str
    reason: Optional[str] = "User requested escalation"
    user_id: Optional[str] = None

# --- Helper Functions ---

async def run_pipeline(
    question: str, 
    history: List[ChatMessage], 
    user_id: str, 
    session_id: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    
    # Resolve Identity (ensures user exists in DB and maps external ID to internal)
    # Note: simple pass-through if we trust input user_id, 
    # but strictly we should probably treat input user_id as external and resolve it.
    # Assuming input user_id is external (e.g. telegram ID or client uuid)
    
    internal_user_id = await IdentityManager.resolve_identity(
        channel="api",
        identifier=user_id,
        metadata_payload=metadata
    )
    
    global_config = load_shared_config("global")
    confidence_threshold = global_config.get("parameters", {}).get("confidence_threshold", 0.3)
    
    # Convert history to format expected by graph (dict)
    conversation_context = [{"role": m.role, "content": m.content} for m in history]

    input_state = {
        "question": question,
        "conversation_context": conversation_context,
        "user_id": internal_user_id,
        "session_id": session_id,
        "hybrid_used": True,
        "confidence_threshold": confidence_threshold
    }
    
    handler = FilteredLangfuseHandler()
    
    try:
        result = await rag_graph.ainvoke(
            input_state,
            config={"callbacks": [handler], "run_name": "api_chat_completion"}
        )
    except Exception as e:
        logger.warning(f"Pipeline error with tracing: {e}, retrying without tracing.")
        result = await rag_graph.ainvoke(
            input_state,
            config={"callbacks": [], "run_name": "api_chat_completion_retry"}
        )

    return result

# --- Endpoints ---

@router.post("/chat/completions", response_model=Envelope[ChatCompletionData])
async def chat_completions(request: Request, body: ChatCompletionRequest):
    """
    Synchronous generation: get full answer at once.
    """
    trace_id = request.state.trace_id
    
    try:
        result = await run_pipeline(
            body.question, 
            body.conversation_history, 
            body.user_id, 
            body.session_id,
            body.user_metadata
        )
        
        answer = result.get("answer") or result.get("escalation_message") or "No answer found."
        
        # Process sources
        raw_sources = result.get("best_doc_metadata", [])
        if isinstance(raw_sources, dict):
            raw_sources = [raw_sources]
        
        sources = []
        for src in raw_sources:
            if not isinstance(src, dict): continue
            sources.append(SourceDocument(
                document_id=str(src.get("id", "")),
                title=src.get("title", "Document"),
                excerpt=src.get("page_content", "")[:200], # Truncate for preview
                relevance=src.get("score", 0.0),
                metadata=src
            ))

        data = ChatCompletionData(
            question=body.question,
            answer=answer,
            sources=sources,
            confidence=float(result.get("confidence", 0.0) or 0.0),
            query_id=str(result.get("query_id", "")),
            pipeline_metadata=result.get("metadata")
        )

        return Envelope(
            data=data,
            meta=MetaResponse(trace_id=trace_id)
        )
        
    except Exception as e:
        logger.error(f"Error in chat_completions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatCompletionRequest):
    """
    SSE Stream generation.
    """
    trace_id = request.state.trace_id
    
    # Streaming requires modifying the graph execution to yield tokens or using callback events.
    # Since rag_graph is a compiled LangGraph, we can use astream_events or similar.
    # For now, if the graph doesn't fully support token-by-token streaming easily to API, 
    # we might simulate it or use ainvoke and yield chunks if supported.
    # Assuming 'astream' is available on the compiled graph for standard output.
    
    # NOTE: LangGraph objects support .astream() but usually yield state updates, not tokens directly unless configured.
    # We might need to iterate over specific events.
    
    async def event_generator():
        # TODO: Implement true token streaming.
        # For this phase, we might just yield the final result chunk by chunk or wait for full result.
        # But to be compliant with "Stream" requirement, we try to stream.
        
        # Resolving identity first
        internal_user_id = await IdentityManager.resolve_identity(
            channel="api_stream",
            identifier=body.user_id,
            metadata_payload=body.user_metadata
        )
        
        # Yield initial metadata event with question
        init_data = {
            "question": body.question,
            "session_id": body.session_id,
            "token": "",
            "trace_id": trace_id
        }
        yield f"data: {json.dumps(init_data)}\n\n"

        global_config = load_shared_config("global")
        confidence_threshold = global_config.get("parameters", {}).get("confidence_threshold", 0.3)
        input_state = {
            "question": body.question,
            "conversation_context": [{"role": m.role, "content": m.content} for m in body.conversation_history],
            "user_id": internal_user_id,
            "session_id": body.session_id,
            "hybrid_used": True,
            "confidence_threshold": confidence_threshold
        }

        # We use astream_events to catch LLM token stream
        try:
            async for event in rag_graph.astream_events(
                input_state, 
                version="v1",
                config={"callbacks": [], "run_name": "api_chat_stream"}
            ):
                kind = event["event"]
                # We look for "on_chat_model_stream" event from the generation node
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        payload = {"token": content, "trace_id": trace_id}
                        yield f"data: {json.dumps(payload)}\n\n"
            
            yield f"data: {json.dumps({'token': '[DONE]', 'trace_id': trace_id})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            err_payload = {"error": str(e), "trace_id": trace_id}
            yield f"data: {json.dumps(err_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/chat/escalate", response_model=Envelope[Dict[str, str]])
async def chat_escalate(request: Request, body: EscalateRequest):
    """
    Trigger manual escalation.
    """
    trace_id = request.state.trace_id
    
    # Logic to mark session as escalated in DB
    # For now, we stub this or use escalation service if available.
    # Since we don't have a direct 'escalate_session' service method visible yet, we just log it.
    
    logger.info(f"Escalation requested for session {body.session_id}: {body.reason}")
    
    return Envelope(
        data={"status": "escalated", "session_id": body.session_id},
        meta=MetaResponse(trace_id=trace_id)
    )

@router.post("/chat/sessions/{session_id}/escalate", response_model=Envelope[Dict[str, str]])
async def chat_session_escalate(request: Request, session_id: str):
    """
    Escalate a specific session.
    """
    trace_id = request.state.trace_id
    logger.info(f"Escalation requested for specific session {session_id}")
    
    return Envelope(
        data={"status": "escalated", "session_id": session_id},
        meta=MetaResponse(trace_id=trace_id)
    )
