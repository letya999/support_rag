"""
LangGraph nodes for cache integration.

These nodes:
1. check_cache_node: Look up query in cache before full pipeline
2. store_in_cache_node: Store generated answer in cache

Integration flow:
    START → check_cache →
      ├─ cache_hit: true → return_cached_answer → END
      └─ cache_hit: false → classify → ... → generate → store_in_cache → END
"""

import time
import uuid_utils
from typing import Optional, Dict, Any
from app.pipeline.state import State
from app.cache.query_normalizer import get_normalizer
from app.cache.cache_layer import get_cache_manager
from app.cache.models import CacheEntry
from app.integrations.embeddings import get_embedding
from app.storage.qdrant_client import get_async_qdrant_client
from qdrant_client.http import models
from app.services.config_loader.loader import get_cache_config

# --- Configuration ---
SEMANTIC_CACHE_COLLECTION = "semantic_cache"
VECTOR_SIZE = 384

def _get_semantic_cache_config() -> Dict[str, Any]:
    """Get semantic cache configuration."""
    try:
        cache_cfg = get_cache_config()
        return cache_cfg.get("semantic", {})
    except Exception:
        return {}

def _get_threshold() -> float:
    """Get similarity threshold for semantic cache hits."""
    cfg = _get_semantic_cache_config()
    return cfg.get("threshold", 0.90)

def _get_ttl_seconds() -> int:
    """Get TTL for semantic cache entries in seconds."""
    cfg = _get_semantic_cache_config()
    return cfg.get("ttl_seconds", 86400)  # Default: 24 hours


async def ensure_semantic_cache_collection(client):
    """Ensure Qdrant collection for semantic cache exists."""
    try:
        collections = await client.get_collections()
        exists = any(c.name == SEMANTIC_CACHE_COLLECTION for c in collections.collections)
        
        if not exists:
            print(f"Creating semantic cache collection: {SEMANTIC_CACHE_COLLECTION}")
            await client.create_collection(
                collection_name=SEMANTIC_CACHE_COLLECTION,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE
                )
            )
    except Exception as e:
        print(f"Failed to ensure semantic cache collection: {e}")


async def cleanup_expired_semantic_cache(client, ttl_seconds: int):
    """
    Remove expired entries from semantic cache.
    Called periodically (e.g., on every Nth request or via scheduled task).
    """
    try:
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
        print(f"🧹 Cleaned up semantic cache entries older than {ttl_seconds}s")
    except Exception as e:
        print(f"⚠️  Semantic cache cleanup failed: {e}")


# Simple counter for periodic cleanup
_request_counter = 0
_CLEANUP_INTERVAL = 100  # Run cleanup every N requests


async def check_cache_node(state: State) -> State:
    """
    Check if query exists in cache (Semantic + Exact).

    Performs:
    1. Query normalization & Exact Match (Redis)
    2. Semantic Search (Qdrant) with TTL filter
    3. Update State
    """
    global _request_counter
    question = state.get("question", "")

    if not question:
        state["cache_hit"] = False
        state["cache_key"] = None
        return state

    try:
        # Initialize components
        normalizer = get_normalizer()
        cache = await get_cache_manager()
        qdrant = get_async_qdrant_client()
        
        # Ensure collection exists (lazy init)
        await ensure_semantic_cache_collection(qdrant)
        
        # Periodic cleanup
        _request_counter += 1
        if _request_counter >= _CLEANUP_INTERVAL:
            _request_counter = 0
            ttl = _get_ttl_seconds()
            await cleanup_expired_semantic_cache(qdrant, ttl)

        # Step 1: Normalize query for Redis key (Exact/Normalized Match)
        cache_key = normalizer.normalize(question)
        state["cache_key"] = cache_key
        
        # 1.1 Exact Match Check (Redis)
        cached_entry = await cache.get(cache_key)
        
        if cached_entry:
            state["cache_hit"] = True
            state["answer"] = cached_entry.answer
            state["confidence"] = 1.0  # Exact match is high confidence
            state["docs"] = cached_entry.doc_ids
            state["cache_reason"] = "exact_match"
            print(f"✅ Exact Cache HIT for: '{question}'")
            return state

        # Step 2: Semantic Search check (Qdrant) with TTL filter
        embedding = await get_embedding(question, is_query=True)
        state["question_embedding"] = embedding  # Save for later storage
        
        # Filter: only consider entries within TTL
        ttl_seconds = _get_ttl_seconds()
        cutoff_time = time.time() - ttl_seconds
        
        # Use query_points which maps to the new Query API.
        # This matches the working implementation in app/nodes/retrieval/storage.py
        
        result = await qdrant.query_points(
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

        threshold = _get_threshold()
        # query_points returns a structure with .points list
        if result and result.points:
            top_match = result.points[0]
            score = top_match.score
            payload = top_match.payload
            
            if score >= threshold:
                state["cache_hit"] = True
                state["answer"] = payload.get("answer")
            
            state["confidence"] = score
            state["docs"] = payload.get("doc_ids", [])
            state["cache_reason"] = f"semantic_match ({score:.2f})"
            
            print(f"✅ Semantic Cache HIT for: '{question}'")
            print(f"   Score: {score:.4f} >= {threshold}")
            return state

        # Cache MISS
        state["cache_hit"] = False
        print(f"❌ Cache MISS for: '{question}'")
        return state

    except Exception as e:
        print(f"⚠️  Cache check error: {e}")
        state["cache_hit"] = False
        return state


async def store_in_cache_node(state: State) -> State:
    """
    Store the generated answer in cache (Redis + Qdrant).
    """
    try:
        # Only store if this was a cache miss
        if state.get("cache_hit", False):
            return state

        answer = state.get("answer")
        cache_key = state.get("cache_key")
        question = state.get("question")
        
        # Try to get embedding from state (preserved from check_cache)
        embedding = state.get("question_embedding")

        if not answer or not cache_key or not question:
            return state

        confidence = state.get("confidence", 0.7)
        docs = state.get("docs", [])
        doc_ids = [d for d in docs if isinstance(d, str)] if docs else []

        # Only cache if confidence is decent
        min_exec_confidence = 0.6
        if confidence < min_exec_confidence:
            print(f"⚠️  Skipping cache: confidence {confidence} < {min_exec_confidence}")
            return state

        # Initialize
        cache = await get_cache_manager()
        qdrant = get_async_qdrant_client()

        # 1. Store in Redis (Exact match)
        cache_entry = CacheEntry(
            query_normalized=cache_key,
            query_original=question,
            answer=answer,
            doc_ids=doc_ids,
            confidence=confidence,
            hit_count=0
        )
        await cache.set(cache_key, cache_entry)
        
        # 2. Store in Qdrant (Semantic match) with timestamp for TTL
        if embedding:
            point_id = str(uuid_utils.uuid7())
            await qdrant.upsert(
                collection_name=SEMANTIC_CACHE_COLLECTION,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "question": question,
                            "original_query": question,
                            "answer": answer,
                            "doc_ids": doc_ids,
                            "timestamp": time.time()
                        }
                    )
                ]
            )
            print(f"💾 Cached semantic vector for: '{question}'")
        else:
            print("⚠️  Missing embedding, skipping semantic cache storage.")

        print(f"💾 Cached answer for: '{question}'")

        return state

    except Exception as e:
        print(f"⚠️  Cache store error: {e}")
        return state


async def get_cache_stats_node(state: State) -> State:
    """Optional: Add cache statistics to state."""
    try:
        cache = await get_cache_manager()
        stats = cache.get_stats()

        if stats:
            state["cache_stats"] = stats.model_dump()

        return state
    except Exception as e:
        print(f"⚠️  Failed to get cache stats: {e}")
        return state
