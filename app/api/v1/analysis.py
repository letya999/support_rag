from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List
from app.api.v1.models import Envelope, MetaResponse
from app.services.webhook_service import WebhookService
import logging

# Rename router tag
router = APIRouter(tags=["Autoclassification categories & intentions"])
logger = logging.getLogger(__name__)

# Models
class ChunkMetadataUpdate(BaseModel):
    chunk_id: str
    metadata: Dict[str, Any]


# Helper Functions
def group_by_category_and_intent(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Group chunks by category and intent for easier analysis.
    
    Returns:
        {
            "categories": [
                {
                    "name": "Category Name",
                    "intents": [
                        {
                            "name": "intent_name",
                            "chunks": [...]
                        }
                    ]
                }
            ]
        }
    """
    from collections import defaultdict
    
    # First level: category -> intents
    category_map = defaultdict(lambda: defaultdict(list))
    
    for chunk in chunks:
        category = chunk.get("metadata", {}).get("category", "Uncategorized")
        intent = chunk.get("metadata", {}).get("intent", "unclassified")
        category_map[category][intent].append(chunk)
    
    # Build structured response
    categories = []
    for cat_name in sorted(category_map.keys()):
        intents_data = []
        for intent_name in sorted(category_map[cat_name].keys()):
            intents_data.append({
                "name": intent_name,
                "count": len(category_map[cat_name][intent_name]),
                "chunks": category_map[cat_name][intent_name]
            })
        
        categories.append({
            "name": cat_name,
            "count": sum(len(chunks) for chunks in category_map[cat_name].values()),
            "intents": intents_data
        })
    
    return {"categories": categories}


# Endpoints

@router.post("/autoclassify/{draft_id}", response_model=Envelope[Dict[str, Any]])
async def classify_draft(
    request: Request, 
    draft_id: str, 
    background_tasks: BackgroundTasks,
    update_staging: bool = False
):
    """
    Auto-classify/Cluster all chunks in a Staging Draft (Redis).
    Uses LLM-based Discovery to generate intents/categories dynamically (clustering).
    Results are grouped by category and intent for easier analysis.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    # 1. Fetch Draft
    from app.services.staging import staging_service
    draft = await staging_service.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    # 2. Process with Discovery Service (LLM Clustering)
    from app.services.classification.discovery_service import DiscoveryService
    service = DiscoveryService()
    
    chunks = draft.get("chunks", [])
    if not chunks:
        return Envelope(data={"categories": []}, meta=MetaResponse(trace_id=trace_id))

    # Send only valid chunks with Q&A
    valid_chunks = [c for c in chunks if c.get("question") and c.get("answer")]
    
    predictions = await service.discover_intents(valid_chunks)
    
    # Map predictions by ID for easy lookup
    pred_map = {p.chunk_id: p for p in predictions}

    # 3. Format Results and Apply Updates
    results = []
    updates_for_staging = []
    
    for chunk in chunks:
        c_id = chunk.get("chunk_id")
        
        # Base object structure
        res_item = {
            "chunk_id": c_id,
            "question": chunk.get("question"),
            "answer": chunk.get("answer"),
            "metadata": chunk.get("metadata", {}).copy() # Copy to avoid mutation issues
        }

        # Apply prediction if available
        if c_id in pred_map:
            pred = pred_map[c_id]
            
            # Update metadata directly with predicted values
            res_item["metadata"]["category"] = pred.category
            res_item["metadata"]["intent"] = pred.intent
            res_item["metadata"]["confidence_score"] = pred.confidence
            
            # Prepare update for Redis if requested
            if update_staging:
                updates_for_staging.append({
                    "chunk_id": c_id,
                    "metadata": {
                        "category": pred.category,
                        "intent": pred.intent,
                        "confidence_score": pred.confidence,
                        "extraction_method": "discovery" # Mark as discovered
                    }
                })
        
        results.append(res_item)
    
    # 4. Update Staging (if requested)
    if update_staging and updates_for_staging:
        await staging_service.update_chunk_metadata_batch(draft_id, updates_for_staging)
    
    # 5. Group by category and intent
    grouped_data = group_by_category_and_intent(results)
    
    # Trigger Webhook
    background_tasks.add_task(
        WebhookService.trigger_outgoing_event,
        event_type="analysis.classification.completed",
        payload={
            "document_id": draft_id,
            "classifications_count": len(predictions),
            "method": "discovery_llm"
        }
    )

    return Envelope(
        data=grouped_data,
        meta=MetaResponse(trace_id=trace_id)
    )


@router.post("/autoclassify/{draft_id}/update", response_model=Envelope[Dict[str, Any]])
async def update_draft_chunks(
    request: Request,
    draft_id: str,
    updates: List[ChunkMetadataUpdate]
):
    """
    Manually update metadata for chunks in a draft (e.g. after user review).
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    from app.services.staging import staging_service
    
    # Convert pydantic models to dicts
    updates_dict = [u.dict() for u in updates]
    
    result = await staging_service.update_chunk_metadata_batch(draft_id, updates_dict)
    
    if not result:
        raise HTTPException(status_code=404, detail="Draft not found or no updates applied")
        
    return Envelope(
        data={"status": "updated", "draft_id": draft_id, "updated_count": len(updates)},
        meta=MetaResponse(trace_id=trace_id)
    )


# ========== Zero-Shot Classification Endpoints ==========

class CategoryIntentInput(BaseModel):
    """Category with nested intents for zero-shot classification."""
    name: str
    intents: List[str]


class ZeroShotSingleRequest(BaseModel):
    """Request model for zero-shot classification of a single draft."""
    update_staging: bool = False


class ZeroShotBatchRequest(BaseModel):
    """Request model for batch zero-shot classification with custom taxonomy."""
    taxonomy: List[CategoryIntentInput]
    draft_ids: List[str]
    update_staging: bool = False



@router.post("/autoclassify/{draft_id}/zeroshot", response_model=Envelope[Dict[str, Any]])
async def classify_draft_zeroshot(
    request: Request,
    draft_id: str,
    background_tasks: BackgroundTasks,
    body: ZeroShotSingleRequest = None
):
    """
    Zero-shot classification of a draft against the System Taxonomy.
    
    Uses the current system taxonomy (categories and intents from TaxonomyService)
    to classify chunks via semantic similarity. Does NOT use LLM to name clusters.
    Results are grouped by category and intent for easier analysis.
    
    Args:
        draft_id: ID of the staging draft to classify
        body: Optional request body with update_staging flag
        
    Returns:
        Grouped structure with categories -> intents -> chunks
    """
    trace_id = getattr(request.state, "trace_id", None)
    update_staging = body.update_staging if body else False
    
    # 1. Fetch Draft
    from app.services.staging import staging_service
    draft = await staging_service.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    chunks = draft.get("chunks", [])
    if not chunks:
        return Envelope(data={"categories": []}, meta=MetaResponse(trace_id=trace_id))
    
    # 2. Get System Taxonomy
    from app.services.taxonomy import TaxonomyService
    taxonomy_service = TaxonomyService()
    categories = await taxonomy_service.get_all_categories()
    
    if not categories:
        raise HTTPException(status_code=400, detail="No system taxonomy found. Please define categories and intents first.")
    
    # Build taxonomy structure
    from app.services.classification.zeroshot_service import CategoryIntent, ZeroShotClassificationService
    
    taxonomy = []
    for cat in categories:
        intents = await taxonomy_service.get_intents_by_category(cat["id"])
        if intents:
            taxonomy.append(CategoryIntent(
                name=cat["name"],
                intents=[i["name"] for i in intents]
            ))
    
    if not taxonomy:
        raise HTTPException(status_code=400, detail="No intents found in system taxonomy")
    
    # 3. Classify using Zero-Shot Service
    service = ZeroShotClassificationService()
    predictions = await service.classify_chunks(chunks, taxonomy)
    
    # 4. Format Results
    pred_map = {p.chunk_id: p for p in predictions}
    results = []
    updates_for_staging = []
    
    for chunk in chunks:
        c_id = chunk.get("chunk_id")
        res_item = {
            "chunk_id": c_id,
            "question": chunk.get("question"),
            "answer": chunk.get("answer"),
            "metadata": chunk.get("metadata", {}).copy()
        }
        
        if c_id in pred_map:
            pred = pred_map[c_id]
            res_item["metadata"]["category"] = pred.category
            res_item["metadata"]["intent"] = pred.intent
            res_item["metadata"]["confidence_score"] = pred.confidence
            
            if update_staging:
                updates_for_staging.append({
                    "chunk_id": c_id,
                    "metadata": {
                        "category": pred.category,
                        "intent": pred.intent,
                        "confidence_score": pred.confidence,
                        "extraction_method": "zeroshot_system"
                    }
                })
        
        results.append(res_item)
    
    # 5. Update Staging if requested
    if update_staging and updates_for_staging:
        await staging_service.update_chunk_metadata_batch(draft_id, updates_for_staging)
    
    # 6. Group by category and intent
    grouped_data = group_by_category_and_intent(results)
    
    # Trigger Webhook
    background_tasks.add_task(
        WebhookService.trigger_outgoing_event,
        event_type="analysis.classification.completed",
        payload={
            "document_id": draft_id,
            "classifications_count": len(predictions),
            "method": "zeroshot_system"
        }
    )

    return Envelope(
        data=grouped_data,
        meta=MetaResponse(trace_id=trace_id)
    )



@router.post("/autoclassify/batch/custom", response_model=Envelope[Dict[str, Any]])
async def classify_batch_custom_taxonomy(
    request: Request,
    body: ZeroShotBatchRequest
):
    """
    Batch zero-shot classification with custom taxonomy.
    
    Classifies multiple drafts against a custom taxonomy provided in the request.
    Does NOT use LLM to name clusters - only semantic similarity matching.
    Results are grouped by category and intent within each draft.
    
    Args:
        body: Request containing custom taxonomy and list of draft IDs
        
    Returns:
        Map of draft_id -> grouped structure (categories -> intents -> chunks)
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    try:
        if not body.taxonomy:
            raise HTTPException(status_code=400, detail="Taxonomy cannot be empty")
        
        if not body.draft_ids:
            raise HTTPException(status_code=400, detail="Draft IDs list cannot be empty")
        
        # Convert input taxonomy
        from app.services.classification.zeroshot_service import CategoryIntent, ZeroShotClassificationService
        
        # Validate intent structure
        taxonomy = []
        for cat in body.taxonomy:
            if not cat.name or not cat.intents:
                continue
            taxonomy.append(CategoryIntent(name=cat.name, intents=cat.intents))
            
        if not taxonomy:
             raise HTTPException(status_code=400, detail="Valid taxonomy is required")
        
        # Process each draft
        from app.services.staging import staging_service
        service = ZeroShotClassificationService()
        
        results_map = {}
        
        for draft_id in body.draft_ids:
            draft = await staging_service.get_draft(draft_id)
            if not draft:
                logger.warning(f"Draft {draft_id} not found, skipping...")
                # Add empty result for missing draft to avoid confusion? 
                # Or just skip. Current behavior is skip.
                continue
            
            chunks = draft.get("chunks", [])
            # Initialize with empty structure if no chunks
            if not chunks:
                results_map[draft_id] = {"categories": []}
                continue
            
            # Classify
            predictions = await service.classify_chunks(chunks, taxonomy)
            pred_map = {p.chunk_id: p for p in predictions}
            
            # Format results and add document_id
            draft_results = []
            updates_for_staging = []
            
            for chunk in chunks:
                c_id = chunk.get("chunk_id")
                # Ensure metadata is a dict
                current_meta = chunk.get("metadata") or {}
                if not isinstance(current_meta, dict):
                    current_meta = {}
                    
                res_item = {
                    "chunk_id": c_id,
                    "document_id": draft_id,  # Add draft_id for tracking
                    "question": chunk.get("question"),
                    "answer": chunk.get("answer"),
                    "metadata": current_meta.copy()
                }
                
                if c_id in pred_map:
                    pred = pred_map[c_id]
                    res_item["metadata"]["category"] = pred.category
                    res_item["metadata"]["intent"] = pred.intent
                    res_item["metadata"]["confidence_score"] = pred.confidence
                    
                    if body.update_staging:
                        updates_for_staging.append({
                            "chunk_id": c_id,
                            "metadata": {
                                "category": pred.category,
                                "intent": pred.intent,
                                "confidence_score": pred.confidence,
                                "extraction_method": "zeroshot_custom_batch"
                            }
                        })
                
                draft_results.append(res_item)

            # Update Staging if requested
            if body.update_staging and updates_for_staging:
                await staging_service.update_chunk_metadata_batch(draft_id, updates_for_staging)
            
            # Group by category and intent
            grouped = group_by_category_and_intent(draft_results)
            results_map[draft_id] = grouped
            
            results_map[draft_id] = grouped
        
        return Envelope(
            data={"drafts": results_map},
            meta=MetaResponse(trace_id=trace_id)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch custom classification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal handling error: {str(e)}")

