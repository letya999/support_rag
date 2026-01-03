#!/usr/bin/env python3
"""
Educational Demo: FAQ Caching with Redis

This script demonstrates:
1. Query normalization (bilingual: RU/EN)
2. Cache hits vs misses
3. Performance metrics
4. Cache statistics

Run with:
    python scripts/demo_cache.py
"""

import asyncio
import time
from app.cache.query_normalizer import QueryNormalizer, get_normalizer
from app.cache.cache_layer import CacheManager
from app.cache.models import CacheEntry
from app.cache.cache_stats import CacheMetrics


async def demo_query_normalization():
    """Demo 1: Show how query normalization works."""
    print("\n" + "=" * 70)
    print("DEMO 1: Query Normalization (Bilingual)")
    print("=" * 70)

    normalizer = QueryNormalizer()

    # English examples
    test_questions_en = [
        "How to reset password?",
        "Reset password, please",
        "password reset?",
        "reset my password please",
        "Please help me reset password",
    ]

    print("\n📌 English Examples:")
    print("-" * 70)
    normalized_en = set()
    for question in test_questions_en:
        normalized = normalizer.normalize(question)
        normalized_en.add(normalized)
        print(f"  '{question}'")
        print(f"    ✓ Normalized to: '{normalized}'")
        print()

    print(f"✅ All {len(test_questions_en)} variations normalize to {len(normalized_en)} unique key(s)")

    # Russian examples
    test_questions_ru = [
        "Как сбросить пароль?",
        "Помогите, сбросить пароль",
        "сбросить пароль пожалуйста",
        "Я забыл пароль, как его сбросить?",
        "Сбросить пароль, помогите!",
    ]

    print("\n📌 Russian Examples:")
    print("-" * 70)
    normalized_ru = set()
    for question in test_questions_ru:
        normalized = normalizer.normalize(question)
        normalized_ru.add(normalized)
        print(f"  '{question}'")
        print(f"    ✓ Normalized to: '{normalized}'")
        print()

    print(f"✅ All {len(test_questions_ru)} variations normalize to {len(normalized_ru)} unique key(s)")

    # Detailed breakdown
    print("\n📌 Detailed Normalization Steps (Example):")
    print("-" * 70)
    example = "How to reset password?"
    details = normalizer.normalize_with_details(example)
    print(f"Original: '{details['original']}'")
    print(f"\nSteps:")
    for step in details["steps"]:
        print(f"  • {step}")
    print(f"\nRemoved stop words: {details['removed_stopwords']}")
    print(f"Final result: '{details['normalized']}'")


async def demo_cache_operations():
    """Demo 2: Cache hit/miss operations."""
    print("\n" + "=" * 70)
    print("DEMO 2: Cache Operations (Hit/Miss)")
    print("=" * 70)

    # Create cache manager (will use in-memory if Redis unavailable)
    cache = await CacheManager.create(
        redis_url="redis://localhost:6379/0",
        max_entries=100,
        ttl_seconds=3600
    )

    # Check health
    health = await cache.health_check()
    print(f"\n🏥 Cache Health: {health['status'].upper()}")
    print(f"   Backend: {health['backend']}")
    print(f"   Entries: {health['total_entries']} / {health['max_entries']}")

    normalizer = get_normalizer()

    # Test data
    faqs = [
        {
            "question": "How to reset password?",
            "answer": "Click on 'Forgot Password' button on the login page. Enter your email and check your inbox for reset link."
        },
        {
            "question": "Как сбросить пароль?",
            "answer": "Нажмите на кнопку 'Забыли пароль?' на странице входа. Введите свой email и проверьте входящие письма."
        },
        {
            "question": "How to check order status?",
            "answer": "Go to 'My Orders' section in your account dashboard. You can track all your orders there."
        }
    ]

    print("\n📝 Storing FAQ entries...")
    print("-" * 70)

    for faq in faqs:
        question = faq["question"]
        normalized = normalizer.normalize(question)

        entry = CacheEntry(
            query_normalized=normalized,
            query_original=question,
            answer=faq["answer"],
            doc_ids=["faq_001", "faq_002"],
            confidence=0.95,
            hit_count=0
        )

        success = await cache.set(normalized, entry)
        print(f"\n💾 Storing: '{question}'")
        print(f"   Key: '{normalized}'")
        print(f"   Status: {'✅ Saved' if success else '❌ Failed'}")

    # Test cache hits
    print("\n\n🔍 Testing Cache Hits:")
    print("-" * 70)

    test_variations = [
        ("How to reset password?", True),  # Exact match
        ("Reset password, please", True),  # Variation
        ("password reset?", True),  # Different order but same keywords
        ("How to check order?", False),  # Cache miss
    ]

    for question, expect_hit in test_variations:
        normalized = normalizer.normalize(question)
        print(f"\n❓ Question: '{question}'")
        print(f"   Normalized key: '{normalized}'")

        start_time = time.time()
        cached = await cache.get(normalized)
        elapsed_ms = (time.time() - start_time) * 1000

        if cached:
            print(f"   ✅ CACHE HIT!")
            print(f"   Answer: '{cached.answer[:50]}...'")
            print(f"   Hit count: {cached.hit_count}")
            print(f"   Response time: {elapsed_ms:.2f}ms")
        else:
            print(f"   ❌ CACHE MISS")
            print(f"   (Would run full pipeline here)")

    # Cleanup
    await cache.close()


async def demo_cache_stats():
    """Demo 3: Cache statistics and metrics."""
    print("\n" + "=" * 70)
    print("DEMO 3: Cache Statistics & Metrics")
    print("=" * 70)

    # Create metrics tracker
    metrics = CacheMetrics(max_top_questions=3)

    print("\n📊 Simulating cache usage...")
    print("-" * 70)

    # Simulate 10 requests (7 hits, 3 misses)
    requests = [
        ("reset password", True, 5.2),      # Hit
        ("check order", False, 850),        # Miss (full pipeline)
        ("reset password", True, 4.8),      # Hit
        ("reset password", True, 5.1),      # Hit
        ("contact support", False, 900),    # Miss
        ("reset password", True, 5.0),      # Hit
        ("check order", True, 5.3),         # Hit (cached after miss)
        ("shipping info", False, 875),      # Miss
        ("reset password", True, 5.2),      # Hit
        ("reset password", True, 4.9),      # Hit
    ]

    for query, is_hit, response_time in requests:
        if is_hit:
            metrics.record_hit(query, response_time)
            print(f"✅ HIT: '{query}' - {response_time:.1f}ms")
        else:
            metrics.record_miss(response_time)
            print(f"❌ MISS: '{query}' - {response_time:.1f}ms")

    # Get stats
    stats = metrics.get_stats()

    print("\n📈 Final Statistics:")
    print("-" * 70)
    print(f"Total Requests:        {stats.total_requests}")
    print(f"Cache Hits:            {stats.cache_hits} ({stats.hit_rate:.1f}%)")
    print(f"Cache Misses:          {stats.cache_misses}")
    print(f"\nResponse Times:")
    print(f"  Avg Cached Response:  {stats.avg_response_time_cached:.2f}ms")
    print(f"  Avg Full Response:    {stats.avg_response_time_full:.2f}ms")
    print(f"  Improvement:          {stats.avg_response_time_full / stats.avg_response_time_cached:.1f}x faster")
    print(f"\nSavings:")
    print(f"  Total Time Saved:     {stats.savings_time:.2f}s")

    print("\n🏆 Top Asked Questions:")
    print("-" * 70)
    if stats.most_asked_questions:
        for i, q in enumerate(stats.most_asked_questions, 1):
            print(f"  {i}. '{q['query']}' - {q['hits']} hits")

    # Print full summary
    print("\n" + "=" * 70)
    print(metrics.get_summary())
    print("=" * 70)


async def main():
    """Run all demos."""
    print("\n" + "🎓 " * 15)
    print("SUPPORT RAG FAQ CACHING - EDUCATIONAL DEMO")
    print("🎓 " * 15)

    try:
        # Demo 1: Query Normalization
        await demo_query_normalization()

        # Demo 2: Cache Operations
        await demo_cache_operations()

        # Demo 3: Statistics
        await demo_cache_stats()

        print("\n" + "=" * 70)
        print("✅ All demos completed successfully!")
        print("=" * 70)
        print("\n📚 Next steps:")
        print("  1. Check app/cache/ directory for implementation")
        print("  2. Run the full pipeline with: uvicorn app.main:app --reload")
        print("  3. Test with: curl 'http://localhost:8000/ask?q=How to reset password'")
        print("  4. Check Redis stats with: redis-cli INFO stats")
        print()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
