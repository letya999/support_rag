from fastapi import APIRouter, Query, HTTPException, Depends, UploadFile, File
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
        # Use escalation_message if answer is not set but escalation was triggered
        answer = result.get("answer") or result.get("escalation_message", "Не смог найти ответ.")
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


# =============================================================================
# Metadata Generation Endpoints
# =============================================================================

@router.post("/documents/metadata-generation/analyze", response_model=dict)
@observe()
async def analyze_qa_metadata(file: UploadFile = None):
    """
    Analyze Q&A JSON file and generate metadata (categories, intents, handoff).

    Uses hybrid approach:
    1. Fast embedding-based classification (no training)
    2. LLM validation for low-confidence predictions
    3. Rule-based handoff detection

    Returns analysis with results ready for user review.
    """
    import json
    import uuid
    from app.services.metadata_generation import HybridMetadataAnalyzer
    from app.cache.cache_layer import get_cache_manager

    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        # Read and validate JSON
        content = await file.read()
        qa_pairs = json.loads(content.decode("utf-8"))

        if not isinstance(qa_pairs, list):
            raise ValueError("JSON must be an array of Q&A pairs")

        if len(qa_pairs) == 0:
            raise ValueError("Q&A pairs array is empty")

        if len(qa_pairs) > 10000:
            raise ValueError("Too many Q&A pairs (max 10,000)")

        # Validate structure
        for idx, pair in enumerate(qa_pairs):
            if not isinstance(pair, dict):
                raise ValueError(f"Item {idx} is not an object")
            if "question" not in pair or "answer" not in pair:
                raise ValueError(f"Item {idx} missing 'question' or 'answer' field")

        # Generate analysis ID
        analysis_id = str(uuid.uuid4())

        # Run analysis
        print(f"[API] Starting metadata analysis for {len(qa_pairs)} Q&A pairs (ID: {analysis_id})")

        analyzer = HybridMetadataAnalyzer()
        await analyzer.initialize()

        result = await analyzer.analyze_batch(qa_pairs, analysis_id)

        # Cache the result
        cache = await get_cache_manager()
        await cache.set(
            f"metadata_analysis:{analysis_id}",
            json.dumps(result.model_dump(), default=str),
            ttl=3600  # 1 hour
        )

        print(f"[API] Analysis complete. Embedding: {result.statistics['embedding_percentage']:.1f}%, LLM: {result.statistics['llm_percentage']:.1f}%")

        return {
            "status": "success",
            "analysis_id": analysis_id,
            "total_items": result.total_pairs,
            "high_confidence": result.high_confidence_count,
            "low_confidence": result.low_confidence_count,
            "llm_validated": result.llm_validated_count,
            "statistics": result.statistics,
            "qa_pairs": [
                {
                    "qa_index": qa.qa_index,
                    "question": qa.question,
                    "answer": qa.answer[:200] + "..." if len(qa.answer) > 200 else qa.answer,
                    "metadata": qa.metadata.model_dump()
                }
                for qa in result.qa_with_metadata
            ]
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error analyzing metadata: {str(e)}")


@router.post("/documents/metadata-generation/review", response_model=dict)
@observe()
async def review_qa_metadata(request: dict):
    """
    Review and apply user corrections to generated metadata.

    Accepts corrections like:
    - Category reassignments
    - Intent corrections
    - Handoff flag changes

    Returns validation status.
    """
    import json
    from app.cache.cache_layer import get_cache_manager

    analysis_id = request.get("analysis_id")
    corrections = request.get("corrections", [])

    if not analysis_id:
        raise HTTPException(status_code=400, detail="analysis_id is required")

    try:
        # Load cached analysis
        cache = await get_cache_manager()
        cached_result = await cache.get(f"metadata_analysis:{analysis_id}")

        if not cached_result:
            raise HTTPException(status_code=404, detail="Analysis not found or expired")

        result_data = json.loads(cached_result)

        # Apply corrections
        for correction in corrections:
            qa_idx = correction.get("qa_index")

            if qa_idx is None or qa_idx >= len(result_data.get("qa_pairs", [])):
                continue

            qa_item = result_data["qa_pairs"][qa_idx]

            # Update metadata
            if "category" in correction:
                qa_item["metadata"]["category"] = correction["category"]

            if "intent" in correction:
                qa_item["metadata"]["intent"] = correction["intent"]

            if "requires_handoff" in correction:
                qa_item["metadata"]["requires_handoff"] = correction["requires_handoff"]

        # Update cache
        await cache.set(
            f"metadata_analysis:{analysis_id}",
            json.dumps(result_data),
            ttl=3600
        )

        return {
            "status": "validated",
            "analysis_id": analysis_id,
            "corrections_applied": len(corrections),
            "total_items": len(result_data.get("qa_pairs", [])),
            "ready_for_ingestion": True
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reviewing metadata: {str(e)}")


@router.post("/documents/metadata-generation/confirm", response_model=dict)
@observe()
async def confirm_qa_metadata(request: dict):
    """
    Confirm and ingest Q&A pairs with generated metadata into database.

    Saves all Q&A pairs with their metadata to PostgreSQL and updates
    the intents registry.
    """
    import json
    from app.cache.cache_layer import get_cache_manager
    from app.services.document_loaders import ProcessedQAPair
    from app.services.ingestion import DocumentIngestionService

    analysis_id = request.get("analysis_id")

    if not analysis_id:
        raise HTTPException(status_code=400, detail="analysis_id is required")

    try:
        # Load cached analysis
        cache = await get_cache_manager()
        cached_result = await cache.get(f"metadata_analysis:{analysis_id}")

        if not cached_result:
            raise HTTPException(status_code=404, detail="Analysis not found or expired")

        result_data = json.loads(cached_result)

        # Prepare pairs for ingestion
        pairs_to_ingest = []
        for qa_item in result_data.get("qa_pairs", []):
            pair = ProcessedQAPair(
                question=qa_item["question"],
                answer=qa_item["answer"],
                metadata=qa_item["metadata"]
            )
            pairs_to_ingest.append(pair)

        # Ingest to database
        print(f"[API] Ingesting {len(pairs_to_ingest)} Q&A pairs with metadata...")

        ingestion_service = DocumentIngestionService()
        result = await ingestion_service.ingest_pairs(pairs_to_ingest)

        # Clear the cache
        await cache.delete(f"metadata_analysis:{analysis_id}")

        print(f"[API] Successfully ingested {result['ingested_count']} Q&A pairs")

        return {
            "status": "success",
            "ingested_count": result["ingested_count"],
            "analysis_id": analysis_id,
            "message": f"Successfully ingested {result['ingested_count']} Q&A pairs with metadata"
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error confirming metadata: {str(e)}")
