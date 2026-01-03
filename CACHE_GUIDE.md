# 🚀 Redis FAQ Caching Guide

A comprehensive caching layer for the Support RAG pipeline that significantly improves response times for frequently asked questions.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Getting Started](#getting-started)
4. [Query Normalization](#query-normalization)
5. [Cache Operations](#cache-operations)
6. [Performance Metrics](#performance-metrics)
7. [Configuration](#configuration)
8. [Examples](#examples)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The caching system provides:

- **🎯 Fast FAQ Lookups**: Reduce response time from ~850ms to ~5ms (170x faster)
- **🌍 Bilingual Support**: Handles both Russian and English queries
- **📊 Performance Monitoring**: Track hit rates, response times, and savings
- **💾 Flexible Storage**: Redis or in-memory fallback
- **🔄 Automatic Integration**: Seamlessly integrates with LangGraph pipeline

### Key Features

| Feature | Benefit |
|---------|---------|
| **Query Normalization** | "How to reset password?" and "reset password please" → same cache key |
| **LRU Eviction** | Automatically removes least-used entries when cache fills |
| **TTL Support** | Entries automatically expire after 24 hours |
| **Metrics Tracking** | Monitor hit rate, time savings, top questions |
| **Graceful Fallback** | Works with in-memory cache if Redis unavailable |

---

## Architecture

### Pipeline Flow

```
┌─────────────────────────────────────────────────────┐
│ User Query: "How to reset password?"                 │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│ check_cache_node                                    │
│  • Normalize query → "reset password"               │
│  • Lookup in Redis                                  │
└─────────────────────────────────────────────────────┘
                          │
                    ┌─────┴─────┐
                    ▼           ▼
              CACHE HIT   CACHE MISS
                    │           │
                    │           ▼
                    │     ┌──────────────┐
                    │     │ Full Pipeline│
                    │     │ • Classify   │
                    │     │ • Retrieve   │
                    │     │ • Rerank     │
                    │     │ • Generate   │
                    │     └──────────────┘
                    │           │
                    └─────┬─────┘
                          ▼
┌─────────────────────────────────────────────────────┐
│ store_in_cache_node                                 │
│  • Store answer in Redis with TTL                   │
│  • Record metrics                                   │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│ Return Answer to User                               │
│ Response Time: 5ms (cached) vs 850ms (full)        │
└─────────────────────────────────────────────────────┘
```

### Component Structure

```
app/cache/
├── __init__.py                 # Module exports
├── models.py                   # Pydantic data models
├── query_normalizer.py         # Bilingual query normalization
├── cache_layer.py              # Redis cache manager
├── cache_stats.py              # Metrics collection
└── nodes.py                    # LangGraph integration nodes
```

---

## Getting Started

### 1. Installation

```bash
# Add Redis to requirements (already done)
pip install redis aioredis

# Or use the existing requirements
pip install -r requirements.txt
```

### 2. Docker Setup

```bash
# Start with Docker Compose (includes Redis)
docker-compose up

# Or start Redis manually
docker run -d -p 6379:6379 redis:7-alpine
```

### 3. Enable in Pipeline

Edit `app/pipeline/pipeline_config.json`:

```json
{
    "cache": {
        "enabled": true,
        "ttl_seconds": 86400,
        "max_entries": 1000,
        "redis_url": "redis://localhost:6379/0"
    },
    "nodes": [ ... ]
}
```

### 4. Test the Cache

```bash
# Run the demo
python scripts/demo_cache.py

# Or test manually
curl 'http://localhost:8000/ask?q=How%20to%20reset%20password'
```

---

## Query Normalization

The key to effective caching is normalizing queries so variations are recognized as the same FAQ.

### Normalization Process

```python
from app.cache.query_normalizer import QueryNormalizer

normalizer = QueryNormalizer()

# Example: Multiple ways to ask the same question
questions = [
    "How to reset password?",
    "Reset password, please",
    "password reset?",
    "reset my password please",
]

# All normalize to the same key
normalized_key = normalizer.normalize(questions[0])
# Output: "password reset"
```

### Normalization Steps

1. **Lowercase**: `"HOW TO RESET PASSWORD?"` → `"how to reset password?"`
2. **Remove Punctuation**: `"how to reset password?"` → `"how to reset password"`
3. **Remove Stop Words**: `"how to reset password"` → `"reset password"`
4. **Sort Keywords**: `"password reset"` → `"password reset"` (same)
5. **Clean Whitespace**: `"  password  reset  "` → `"password reset"`

### Bilingual Stop Words

**English**: how, what, can, please, me, my, do, does, should, etc.

**Russian**: как, что, можно, пожалуйста, я, мой, делать, и т.д.

### Example: Detailed Normalization

```python
details = normalizer.normalize_with_details("How to reset password?")

# Output:
# {
#     "original": "How to reset password?",
#     "normalized": "password reset",
#     "steps": [
#         "Lowercase: 'How to reset password?' -> 'how to reset password?'",
#         "Remove punctuation: 'how to reset password?' -> 'how to reset password'",
#         "Tokens: ['how', 'to', 'reset', 'password']",
#         "Remove stop words: [('how', 'English'), ('to', 'English')]",
#         "Sort tokens: ['password', 'reset']"
#     ],
#     "removed_stopwords": [("how", "English"), ("to", "English")]
# }
```

---

## Cache Operations

### Initialize Cache Manager

```python
from app.cache.cache_layer import get_cache_manager

# Get global cache instance
cache = await get_cache_manager(redis_url="redis://localhost:6379/0")
```

### Store Entry

```python
from app.cache.models import CacheEntry

entry = CacheEntry(
    query_normalized="reset password",
    query_original="How to reset password?",
    answer="Click on 'Forgot Password'...",
    doc_ids=["doc_1", "doc_2"],
    confidence=0.95,
)

success = await cache.set("reset password", entry)
```

### Retrieve Entry

```python
cached = await cache.get("reset password")

if cached:
    print(f"Answer: {cached.answer}")
    print(f"Hit count: {cached.hit_count}")
    print(f"Confidence: {cached.confidence}")
else:
    print("Not in cache")
```

### Delete Entry

```python
deleted = await cache.delete("reset password")
```

### Clear All

```python
await cache.clear()
```

### Get All Entries

```python
all_entries = await cache.get_all_entries()

for key, entry in all_entries.items():
    print(f"{key}: {entry.answer[:50]}...")
```

---

## Performance Metrics

### Track Performance

```python
from app.cache.cache_stats import CacheMetrics

metrics = CacheMetrics()

# Record a cache hit (fast response)
metrics.record_hit("reset password", response_time_ms=5.2)

# Record a cache miss (full pipeline)
metrics.record_miss(response_time_ms=850)

# Get statistics
stats = metrics.get_stats()
```

### Statistics Available

```python
stats = metrics.get_stats()

print(f"Hit Rate: {stats.hit_rate}%")
print(f"Total Requests: {stats.total_requests}")
print(f"Cache Hits: {stats.cache_hits}")
print(f"Cache Misses: {stats.cache_misses}")
print(f"Avg Cached Response: {stats.avg_response_time_cached}ms")
print(f"Avg Full Response: {stats.avg_response_time_full}ms")
print(f"Time Saved: {stats.savings_time}s")
print(f"Memory Usage: {stats.memory_usage_mb}MB")

# Top questions
for q in stats.most_asked_questions:
    print(f"  {q['query']}: {q['hits']} hits")
```

### Human-Readable Summary

```python
print(metrics.get_summary())

# Output:
# 📊 Cache Performance Summary
# ─────────────────────────────
# Total Requests: 100
# Cache Hits: 45 (45.00%)
# Cache Misses: 55
# Avg Cached Response: 5.20ms
# Avg Full Response: 850.00ms
# Time Saved: 37.88s
# Memory: 2.5 MB
#
# Top Questions:
#   1. "reset password" (15 hits)
#   2. "check order status" (12 hits)
#   3. "contact support" (8 hits)
```

---

## Configuration

### Pipeline Configuration

Edit `app/pipeline/pipeline_config.json`:

```json
{
    "cache": {
        "enabled": true,
        "ttl_seconds": 86400,
        "max_entries": 1000,
        "redis_url": "redis://localhost:6379/0"
    },
    "nodes": [
        { "name": "fasttext_classify", "enabled": true },
        { "name": "hybrid_search", "enabled": true },
        { "name": "generate", "enabled": true }
    ]
}
```

### Environment Variables

```bash
# .env file
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_ENTRIES=1000
REDIS_TTL_SECONDS=86400
```

### Cache Manager Options

```python
cache = await CacheManager.create(
    redis_url="redis://localhost:6379/0",
    max_entries=1000,        # LRU limit
    ttl_seconds=86400,       # 24 hours
    enable_stats=True        # Track metrics
)
```

---

## Examples

### Example 1: Basic Usage

```python
import asyncio
from app.cache.cache_layer import get_cache_manager
from app.cache.query_normalizer import get_normalizer
from app.cache.models import CacheEntry

async def main():
    cache = await get_cache_manager()
    normalizer = get_normalizer()

    # Normalize a question
    question = "How to reset password?"
    cache_key = normalizer.normalize(question)

    # Create a cache entry
    entry = CacheEntry(
        query_normalized=cache_key,
        query_original=question,
        answer="Click 'Forgot Password' button...",
        doc_ids=["faq_001"],
        confidence=0.95
    )

    # Store it
    await cache.set(cache_key, entry)

    # Retrieve it
    cached = await cache.get(cache_key)
    print(f"Answer: {cached.answer}")

asyncio.run(main())
```

### Example 2: Monitoring Hit Rate

```python
from app.cache.cache_stats import CacheMetrics

metrics = CacheMetrics()

# Simulate usage
metrics.record_hit("reset password", 5.2)
metrics.record_hit("reset password", 5.1)
metrics.record_miss(850)
metrics.record_hit("order status", 5.3)
metrics.record_miss(875)

stats = metrics.get_stats()

print(f"Hit Rate: {stats.hit_rate}%")
print(f"Questions Served: {len(stats.most_asked_questions)}")
print(f"Time Saved: {stats.savings_time}s")
```

### Example 3: Bilingual Support

```python
normalizer = QueryNormalizer()

# English
en_queries = [
    "How to reset password?",
    "reset password please",
    "password reset?",
]

# Russian
ru_queries = [
    "Как сбросить пароль?",
    "сбросить пароль пожалуйста",
    "сбросить пароль?",
]

en_normalized = set(normalizer.normalize(q) for q in en_queries)
ru_normalized = set(normalizer.normalize(q) for q in ru_queries)

print(f"English variations: {len(en_queries)} → {len(en_normalized)} unique key(s)")
print(f"Russian variations: {len(ru_queries)} → {len(ru_normalized)} unique key(s)")

# Example output:
# English variations: 3 → 1 unique key(s)
# Russian variations: 3 → 1 unique key(s)
```

---

## Troubleshooting

### Redis Connection Issues

```python
# Check health
health = await cache.health_check()
print(health)

# If unhealthy, cache will use in-memory fallback
# Check logs: "Redis connection failed... Using in-memory cache"
```

### Cache Not Storing

1. **Confidence too low**: Only caches if confidence ≥ 0.6
2. **Redis unavailable**: Falls back to in-memory
3. **Cache disabled**: Check `pipeline_config.json`

### Memory Issues

```python
# Monitor memory usage
stats = cache.get_stats()
print(f"Memory: {stats.memory_usage_mb}MB")

# Clear old entries
await cache.clear()

# Or increase Redis memory:
# redis-cli CONFIG SET maxmemory 512mb
```

### Slow Response Times

1. **Check hit rate**: `stats.hit_rate`
2. **Check normalization**: Are queries normalizing correctly?
3. **Verify Redis**: `redis-cli ping`
4. **Check network**: Between app and Redis

### Testing

```bash
# Run tests
pytest tests/test_cache.py -v

# Run demo
python scripts/demo_cache.py

# Check Redis
redis-cli INFO stats
redis-cli KEYS "faq_cache:*"
redis-cli GET "faq_cache:reset password"
```

---

## Performance Expectations

### Typical Benchmarks

| Scenario | Response Time | Speedup |
|----------|---------------|---------|
| Cache Hit | 5-10 ms | 100x faster |
| Cache Miss (Full Pipeline) | 800-1000 ms | — |
| With 50% Hit Rate | ~400-500 ms avg | 2x faster |

### Hit Rate Factors

- **FAQ Quality**: Better FAQs = better caching
- **Query Patterns**: Repetitive queries = higher hit rate
- **Normalization**: Better normalization = more hits
- **TTL Setting**: Longer TTL = better hit rate (but stale data)

---

## Advanced Topics

### Custom Cache Keys

```python
# Instead of auto-normalization, use custom keys
cache_key = "password_reset_en"  # Explicit key
await cache.set(cache_key, entry)
```

### Cache Warming

```python
# Pre-populate cache with FAQs
faqs = load_faq_database()
for faq in faqs:
    key = normalizer.normalize(faq.question)
    entry = CacheEntry(...)
    await cache.set(key, entry)
```

### Cache Eviction

```python
# Manual LRU eviction
all_entries = await cache.get_all_entries()
if len(all_entries) > max_size:
    # Remove least-used
    min_entry = min(all_entries.items(),
                    key=lambda x: x[1].hit_count)
    await cache.delete(min_entry[0])
```

### Distributed Caching

Use Redis Cluster for distributed systems:

```python
cache = await CacheManager.create(
    redis_url="redis-cluster://node1:6379,node2:6379"
)
```

---

## Next Steps

1. **Enable caching** in `pipeline_config.json`
2. **Run demo** to understand the system
3. **Monitor metrics** with `get_stats()`
4. **Tune parameters** based on your FAQ patterns
5. **Integrate monitoring** (e.g., with Langfuse)

---

## References

- [Redis Documentation](https://redis.io/documentation)
- [Aioredis Library](https://github.com/aio-libs/aioredis-py)
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph/)
- [Project README](README.md)

---

**Happy Caching! 🚀**
