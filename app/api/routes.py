from fastapi import APIRouter, Query, HTTPException, Depends
from urllib.parse import unquote
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.settings import settings
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Configuration Endpoints
# =============================================================================

@router.get("/config/system-phrases")
async def get_system_phrases():
    """
    Get system phrases for Telegram bot.
    
    Returns filter patterns and display phrases.
    Telegram bot should call this on startup and cache the result.
    """
    try:
        from app.services.config_loader.loader import load_shared_config
        config = load_shared_config("system_phrases")
        return {
            "version": config.get("version", "1.0"),
            "filter_patterns": config.get("filter_patterns", []),
            "display_phrases": config.get("display_phrases", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {e}")


@router.get("/config/languages")
async def get_languages():
    """
    Get language configuration.
    
    Returns supported languages and detection settings.
    """
    try:
        from app.services.config_loader.loader import load_shared_config
        config = load_shared_config("languages")
        return {
            "version": config.get("version", "1.0"),
            "detection": config.get("detection", {}),
            "response": config.get("response", {}),
            "supported": config.get("supported", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {e}")


@router.post("/config/reload")
async def reload_config():
    """
    Hot-reload all cached configurations.
    
    Call this after updating YAML config files to apply changes
    without restarting the server.
    """
    try:
        from app.services.config_loader.loader import clear_config_cache
        from app.nodes._shared_config.history_filter import clear_filter_cache
        
        # Clear config caches
        clear_config_cache()
        clear_filter_cache()
        
        return {
            "status": "ok",
            "message": "All configuration caches cleared"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload config: {e}")


# Document upload and ingestion endpoints
@router.post("/documents/upload", response_model=dict)
@observe()
async def upload_documents(files: list = None):
    """Upload and process documents for Q&A extraction.

    Accepts up to 5 documents in formats: PDF, DOCX, CSV, Markdown.
    Returns extracted Q&A pairs for confirmation before ingestion.
    """
    import asyncio
    from fastapi import UploadFile, File

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 files per upload")

    try:
        from app.services.batch_processors import DocumentBatchProcessor
        import tempfile
        import os

        # Save uploaded files temporarily
        temp_dir = tempfile.mkdtemp()
        file_paths = []

        for file in files:
            if not file:
                continue

            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())
            file_paths.append(file_path)

        # Process batch
        processor = DocumentBatchProcessor()
        result = await processor.process_batch(
            file_paths,
            auto_confirm=False,
            confidence_threshold=0.6,
            skip_duplicates=True
        )

        # Clean up temp files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Convert result to response format
        return {
            "total_files": result.total_files,
            "processed_files": result.processed_files,
            "failed_files": [
                {
                    "file_name": f.file_name,
                    "error_type": f.error_type,
                    "error_message": f.error_message
                }
                for f in result.failed_files
            ],
            "qa_pairs": [p.to_dict() for p in result.qa_pairs],
            "warnings": result.warnings,
            "summary": result.summary
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing documents: {str(e)}")


@router.post("/documents/confirm", response_model=dict)
@observe()
async def confirm_upload(request: dict):
    """Confirm and ingest Q&A pairs into the vector store.

    Takes validated Q&A pairs and stores them in PostgreSQL and Qdrant.
    """
    try:
        from app.services.ingestion import DocumentIngestionService
        from app.services.document_loaders import ProcessedQAPair

        qa_pairs_data = request.get("qa_pairs", [])

        if not qa_pairs_data:
            raise HTTPException(status_code=400, detail="No Q&A pairs provided")

        # Convert to ProcessedQAPair objects
        pairs = []
        for pair_data in qa_pairs_data:
            pair = ProcessedQAPair(
                question=pair_data.get("question", ""),
                answer=pair_data.get("answer", ""),
                metadata=pair_data.get("metadata", {})
            )
            pairs.append(pair)

        # Ingest to database
        result = await DocumentIngestionService.ingest_pairs(pairs)

        return {
            "status": result["status"],
            "ingested_count": result["ingested_count"],
            "message": f"Successfully ingested {result['ingested_count']} Q&A pairs"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting documents: {str(e)}")
