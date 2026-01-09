from fastapi import APIRouter, HTTPException, UploadFile, File
from app.observability.tracing import observe
import json
import uuid
from app.services.metadata_generation import AutoClassificationPipeline, HandoffDetector
from app.services.cache.manager import get_cache_manager
from app.services.document_loaders import ProcessedQAPair
from app.services.ingestion import DocumentIngestionService

router = APIRouter()

@router.post("/analyze", response_model=dict)
@observe()
async def analyze_qa_metadata(file: UploadFile = None):
    """
    Analyze Q&A JSON file and generate metadata (categories, intents, handoff).

    Uses CPU-first approach:
    1. Sentence-transformers for embeddings
    2. Sklearn clustering for category discovery
    3. TF-IDF + patterns for naming
    4. LLM validation ONLY for low-confidence cases

    Returns analysis with results ready for user review.
    """
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

        # Validate structure - accept both simple and extended formats
        for idx, pair in enumerate(qa_pairs):
            if not isinstance(pair, dict):
                raise ValueError(f"Item {idx} is not an object")
            if "question" not in pair or "answer" not in pair:
                raise ValueError(f"Item {idx} missing 'question' or 'answer' field")

        # Generate analysis ID
        analysis_id = str(uuid.uuid4())

        # Run classification
        print(f"[API] Starting auto-classification for {len(qa_pairs)} Q&A pairs (ID: {analysis_id})")

        classifier = AutoClassificationPipeline(
            embedding_model="all-MiniLM-L6-v2",
            distance_threshold=0.7,
            confidence_threshold=0.65,
            llm_validation_threshold=0.4
        )
        
        handoff_detector = HandoffDetector()

        # Run classification pipeline
        classification_results, discovered_categories = await classifier.classify_batch(
            qa_pairs,
            use_llm_validation=True
        )
        
        # Get handoff detection
        handoff_results = handoff_detector.detect_batch(qa_pairs)

        # Build response with metadata
        qa_with_metadata = []
        high_confidence_count = 0
        low_confidence_count = 0
        
        for idx, (qa, clf_result, handoff) in enumerate(zip(qa_pairs, classification_results, handoff_results)):
            metadata = {
                "category": clf_result.category,
                "intent": clf_result.intent,
                "requires_handoff": handoff["requires_handoff"],
                "confidence_threshold": handoff["confidence_threshold"],
                "clarifying_questions": handoff["clarifying_questions"],
                "confidence_scores": {
                    "category": clf_result.category_confidence,
                    "intent": clf_result.intent_confidence,
                    "validation_method": "llm" if clf_result.needs_llm_validation else "embedding"
                }
            }
            
            if clf_result.category_confidence >= 0.65:
                high_confidence_count += 1
            else:
                low_confidence_count += 1
            
            qa_with_metadata.append({
                "qa_index": idx,
                "question": qa["question"],
                "answer": qa["answer"][:200] + "..." if len(qa["answer"]) > 200 else qa["answer"],
                "metadata": metadata
            })

        # Prepare result for caching
        result_data = {
            "analysis_id": analysis_id,
            "total_pairs": len(qa_pairs),
            "high_confidence_count": high_confidence_count,
            "low_confidence_count": low_confidence_count,
            "discovered_categories": [
                {"name": cat.name, "keywords": cat.keywords, "question_count": len(cat.member_indices)}
                for cat in discovered_categories
            ],
            "qa_pairs": [
                {
                    "qa_index": item["qa_index"],
                    "question": qa_pairs[item["qa_index"]]["question"],
                    "answer": qa_pairs[item["qa_index"]]["answer"],
                    "metadata": item["metadata"]
                }
                for item in qa_with_metadata
            ]
        }

        # Cache the result
        cache = await get_cache_manager()
        await cache.set(
            f"metadata_analysis:{analysis_id}",
            json.dumps(result_data, default=str),
            ttl=3600  # 1 hour
        )

        print(f"[API] Analysis complete. {len(discovered_categories)} categories discovered.")

        return {
            "status": "success",
            "analysis_id": analysis_id,
            "total_items": len(qa_pairs),
            "high_confidence": high_confidence_count,
            "low_confidence": low_confidence_count,
            "discovered_categories": result_data["discovered_categories"],
            "statistics": {
                "total_items": len(qa_pairs),
                "categories_discovered": len(discovered_categories),
                "high_confidence_percentage": (high_confidence_count / len(qa_pairs)) * 100 if qa_pairs else 0,
                "handoff_count": sum(1 for h in handoff_results if h["requires_handoff"])
            },
            "qa_pairs": qa_with_metadata
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error analyzing metadata: {str(e)}")


@router.post("/review", response_model=dict)
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


@router.post("/confirm", response_model=dict)
@observe()
async def confirm_qa_metadata(request: dict):
    """
    Confirm and ingest Q&A pairs with generated metadata into database.

    Saves all Q&A pairs with their metadata to PostgreSQL and updates
    the intents registry.
    """
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
