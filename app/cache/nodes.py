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
from typing import Optional
from app.pipeline.state import State
from app.cache.query_normalizer import get_normalizer
from app.cache.cache_layer import get_cache_manager
from app.cache.models import CacheEntry


async def check_cache_node(state: State) -> State:
    """
    Check if query exists in cache.

    Performs:
    1. Query normalization
    2. Cache lookup
    3. Metrics recording

    Args:
        state: Pipeline state

    Returns:
        Updated state with cache_hit, cache_key fields

    Example:
        state = {
            "question": "How to reset password?",
            ...
        }
        state = await check_cache_node(state)
        # If cached: state["cache_hit"] = True, state["answer"] = cached_answer
        # If not: state["cache_hit"] = False
    """
    question = state.get("question", "")

    if not question:
        state["cache_hit"] = False
        state["cache_key"] = None
        return state

    try:
        # Initialize components
        normalizer = get_normalizer()
        cache = await get_cache_manager()

        # Step 1: Normalize query
        cache_key = normalizer.normalize(question)
        state["cache_key"] = cache_key

        # Step 2: Look up in cache
        start_time = time.time()
        cached_entry = await cache.get(cache_key)
        response_time_ms = (time.time() - start_time) * 1000

        if cached_entry:
            # Cache HIT
            state["cache_hit"] = True
            state["answer"] = cached_entry.answer
            state["confidence"] = cached_entry.confidence
            state["docs"] = cached_entry.doc_ids

            # Record metrics
            if cache.metrics:
                cache.metrics.record_hit(
                    query_normalized=cache_key,
                    response_time_ms=response_time_ms,
                    doc_ids=cached_entry.doc_ids
                )

            print(f"✅ Cache HIT for: '{question}'")
            print(f"   Normalized: '{cache_key}'")
            print(f"   Response time: {response_time_ms:.2f}ms")
            print(f"   Hit count: {cached_entry.hit_count}")

            return state
        else:
            # Cache MISS
            state["cache_hit"] = False
            print(f"❌ Cache MISS for: '{question}'")
            print(f"   Normalized: '{cache_key}'")
            print(f"   Will execute full pipeline...")

            return state

    except Exception as e:
        print(f"⚠️  Cache check error: {e}")
        state["cache_hit"] = False
        return state


async def store_in_cache_node(state: State) -> State:
    """
    Store the generated answer in cache.

    Performs:
    1. Build CacheEntry from state
    2. Store in cache
    3. Update metrics

    Args:
        state: Pipeline state with answer

    Returns:
        Updated state

    Conditions:
    - Only stores if question was generated (cache_hit = False)
    - Only stores if answer exists
    - Only stores if confidence is acceptable

    Example:
        state = {
            "question": "How to reset password?",
            "answer": "Click on Forgot Password...",
            "confidence": 0.95,
            "docs": ["doc_1"],
            "cache_key": "reset password",
            "cache_hit": False,
            ...
        }
        state = await store_in_cache_node(state)
        # Answer is now cached for future queries
    """
    try:
        # Only store if this was a cache miss (not from cache)
        if state.get("cache_hit", False):
            return state

        # Required fields
        answer = state.get("answer")
        cache_key = state.get("cache_key")
        question = state.get("question")

        if not answer or not cache_key:
            return state

        # Extract data
        confidence = state.get("confidence", 0.7)
        docs = state.get("docs", [])

        # Filter docs to IDs only (strings)
        doc_ids = [d for d in docs if isinstance(d, str)] if docs else []

        # Only cache if confidence is above threshold
        min_confidence = 0.6
        if confidence < min_confidence:
            print(f"⚠️  Skipping cache: confidence {confidence} < {min_confidence}")
            return state

        # Initialize components
        cache = await get_cache_manager()

        # Create cache entry
        cache_entry = CacheEntry(
            query_normalized=cache_key,
            query_original=question,
            answer=answer,
            doc_ids=doc_ids,
            confidence=confidence,
            hit_count=0  # First storage
        )

        # Store in cache
        start_time = time.time()
        success = await cache.set(cache_key, cache_entry)
        response_time_ms = (time.time() - start_time) * 1000

        if success:
            print(f"💾 Cached answer for: '{question}'")
            print(f"   Key: '{cache_key}'")
            print(f"   Confidence: {confidence:.2f}")
            print(f"   Store time: {response_time_ms:.2f}ms")

            # Record metrics
            if cache.metrics:
                cache.metrics.record_miss(response_time_ms=response_time_ms)
        else:
            print(f"❌ Failed to cache answer for: '{question}'")

        return state

    except Exception as e:
        print(f"⚠️  Cache store error: {e}")
        return state


async def get_cache_stats_node(state: State) -> State:
    """
    Optional: Add cache statistics to state.

    Useful for monitoring and debugging.

    Args:
        state: Pipeline state

    Returns:
        State with cache_stats field
    """
    try:
        cache = await get_cache_manager()
        stats = cache.get_stats()

        if stats:
            state["cache_stats"] = stats.model_dump()

        return state
    except Exception as e:
        print(f"⚠️  Failed to get cache stats: {e}")
        return state
