"""
Semantic Similarity Cache Service.

Provides semantic search functionality for cache using Qdrant.
Refactored from app/cache/nodes.py to follow services pattern.
"""

import time
from typing import Optional, Dict, Any, List
from qdrant_client.http import models
from app.logging_config import logger
from app.integrations.embeddings import get_embedding
from app.storage.qdrant_client import get_async_qdrant_client
from app.services.config_loader.loader import load_shared_config

# Configuration
SEMANTIC_CACHE_COLLECTION = "semantic_cache"
VECTOR_SIZE = 384


def _get_semantic_cache_config() -> Dict[str, Any]:
    """Get semantic cache configuration from shared config."""
    try:
        cache_cfg = load_shared_config("cache")
        params = cache_cfg.get("parameters", {})
        return params.get("semantic", {})
    except Exception:
        return {}


def get_similarity_threshold() -> float:
    """Get similarity threshold for semantic cache hits."""
    cfg = _get_semantic_cache_config()
    return cfg.get("threshold", 0.92)  # Default: 0.92


def get_ttl_seconds() -> int:
    """Get TTL for semantic cache entries in seconds."""
    cfg = _get_semantic_cache_config()
    return cfg.get("ttl_seconds", 86400)  # Default: 24 hours


async def ensure_semantic_cache_collection():
    """Ensure Qdrant collection for semantic cache exists."""
    try:
        client = get_async_qdrant_client()
        collections = await client.get_collections()
        exists = any(c.name == SEMANTIC_CACHE_COLLECTION for c in collections.collections)
        
        if not exists:
            logger.info("Creating semantic cache collection", extra={"collection": SEMANTIC_CACHE_COLLECTION})
            await client.create_collection(
                collection_name=SEMANTIC_CACHE_COLLECTION,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE
                )
            )
    except Exception as e:
        logger.error("Failed to ensure semantic cache collection", extra={"error": str(e)})


async def cleanup_expired_semantic_cache(ttl_seconds: int):
    """
    Remove expired entries from semantic cache.
    Called periodically (e.g., on every Nth request or via scheduled task).
    """
    try:
        client = get_async_qdrant_client()
        cutoff_time = time.time() - ttl_seconds
        
        # Delete points where timestamp < cutoff_time
        await client.delete(
            collection_name=SEMANTIC_CACHE_COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="timestamp",
                            range=models.Range(lt=cutoff_time)
                        )
                    ]
                )
            )
        )
        logger.info("Cleaned up expired semantic cache entries", extra={"ttl_seconds": ttl_seconds})
    except Exception as e:
        logger.warning("Semantic cache cleanup failed", extra={"error": str(e)})


async def check_semantic_similarity(
    question: str,
    translated_query: Optional[str] = None,
    similarity_threshold: Optional[float] = None,
    use_translation: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Check semantic similarity against cached queries using Qdrant.
    
    Args:
        question: Original query
        translated_query: English translation of query (optional)
        similarity_threshold: Custom threshold (optional, uses config default if None)
        use_translation: Whether to use translated query for comparison
        
    Returns:
        Dictionary with cache hit data if found, None otherwise.
        Format: {
            "answer": str,
            "doc_ids": List[str],
            "score": float,
            "cached_question": str
        }
    """
    try:
        client = get_async_qdrant_client()
        
        # Ensure collection exists
        await ensure_semantic_cache_collection()
        
        # Decide which text to use for embedding
        query_text = translated_query if (use_translation and translated_query) else question
        
        # Get embedding
        embedding = await get_embedding(query_text, is_query=True)
        
        # Get threshold
        threshold = similarity_threshold if similarity_threshold is not None else get_similarity_threshold()
        
        # Filter: only consider entries within TTL
        ttl_seconds = get_ttl_seconds()
        cutoff_time = time.time() - ttl_seconds
        
        # Search in Qdrant
        result = await client.query_points(
            collection_name=SEMANTIC_CACHE_COLLECTION,
            query=embedding,
            limit=1,
            with_payload=True,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="timestamp",
                        range=models.Range(gte=cutoff_time)
                    )
                ]
            )
        )
        
        # Check if we have a match above threshold
        if result and result.points:
            top_match = result.points[0]
            score = top_match.score
            payload = top_match.payload
            
            if score >= threshold:
                return {
                    "answer": payload.get("answer"),
                    "doc_ids": payload.get("doc_ids", []),
                    "score": score,
                    "cached_question": payload.get("question", "")
                }
            else:
                logger.debug("Semantic score below threshold", extra={"score": score, "threshold": threshold})
        
        return None
        
    except Exception as e:
        logger.error("Semantic similarity check error", extra={"error": str(e)})
        return None


async def store_in_semantic_cache(
    question: str,
    answer: str,
    doc_ids: List[str],
    embedding: List[float],
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Store entry in semantic cache (Qdrant).
    
    Args:
        question: Original question
        answer: Generated answer
        doc_ids: List of document IDs used
        embedding: Question embedding vector
        metadata: Optional additional metadata (e.g., translated_query)
    """
    try:
        import uuid_utils
        client = get_async_qdrant_client()
        
        # Prepare payload
        payload = {
            "question": question,
            "answer": answer,
            "doc_ids": doc_ids,
            "timestamp": time.time()
        }
        
        # Add metadata if provided
        if metadata:
            payload.update(metadata)
        
        # Store in Qdrant
        point_id = str(uuid_utils.uuid7())
        await client.upsert(
            collection_name=SEMANTIC_CACHE_COLLECTION,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                )
            ]
        )
        logger.info("Stored question in semantic cache", extra={"question": question})
        
    except Exception as e:
        logger.error("Semantic cache store error", extra={"error": str(e)})
