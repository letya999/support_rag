# API Cache Examples

Examples of using the Support RAG API with caching enabled.

## Quick Start

```bash
# Start the API
uvicorn app.main:app --reload

# Test cache status
curl http://localhost:8000/cache/status

# Ask a question (will cache the answer)
curl "http://localhost:8000/ask?q=How%20to%20reset%20password"

# Ask same question again (will hit cache)
curl "http://localhost:8000/ask?q=How%20to%20reset%20password"
```

## Endpoints

### 1. Ask (with Cache)

**Endpoint**: `GET /ask`

**Parameters**:
- `q`: Question to answer
- `hybrid`: Enable hybrid search (default: true)

**Example**:
```bash
curl "http://localhost:8000/ask?q=How%20to%20reset%20password"
```

**Response**:
```json
{
  "answer": "Click on 'Forgot Password' button on the login page..."
}
```

**What happens**:
1. Question is normalized: "How to reset password?" → "reset password"
2. Cache is checked for "reset password"
3. If found → return cached answer (5-10ms)
4. If not found → run full pipeline (800-1000ms) and cache result

---

### 2. Cache Status

**Endpoint**: `GET /cache/status`

**Example**:
```bash
curl http://localhost:8000/cache/status
```

**Response**:
```json
{
  "health": {
    "status": "healthy",
    "backend": "redis",
    "total_entries": 12,
    "max_entries": 1000,
    "ttl_seconds": 86400
  },
  "stats": {
    "total_requests": 100,
    "cache_hits": 45,
    "cache_misses": 55,
    "hit_rate": 45.0,
    "avg_response_time_cached": 5.2,
    "avg_response_time_full": 850.0,
    "savings_time": 37.5,
    "memory_usage_mb": 2.5,
    "total_entries": 12,
    "most_asked_questions": [
      {
        "query": "reset password",
        "hits": 15
      },
      {
        "query": "check order status",
        "hits": 12
      }
    ]
  }
}
```

---

## Examples by Language

### English Example

```bash
# First request (cache miss, full pipeline)
curl "http://localhost:8000/ask?q=How%20do%20I%20reset%20my%20password" \
  -H "Content-Type: application/json" \
  -w "\nTime: %{time_total}s\n"
# Time: 0.850s

# Second request (cache hit)
curl "http://localhost:8000/ask?q=How%20to%20reset%20password" \
  -H "Content-Type: application/json" \
  -w "\nTime: %{time_total}s\n"
# Time: 0.005s ✨

# Third variation (normalized to same key, cache hit)
curl "http://localhost:8000/ask?q=reset%20password%20please" \
  -H "Content-Type: application/json" \
  -w "\nTime: %{time_total}s\n"
# Time: 0.005s ✨
```

**Notes**:
- All three questions normalize to: "password reset"
- Questions 2 and 3 hit the cache despite different wording
- 170x speedup on cached queries

### Russian Example

```bash
# First request (cache miss)
curl "http://localhost:8000/ask?q=Как%20сбросить%20пароль" \
  -w "\nTime: %{time_total}s\n"
# Time: 0.850s

# Second request (cache hit - bilingual support!)
curl "http://localhost:8000/ask?q=сбросить%20пароль%20пожалуйста" \
  -w "\nTime: %{time_total}s\n"
# Time: 0.005s ✨
```

**Notes**:
- Russian queries are normalized just like English
- Both normalize to: "пароль сбросить"
- Bilingual normalization works seamlessly

---

## Performance Monitoring

### Monitor Cache in Real-Time

```bash
#!/bin/bash

echo "Monitoring cache performance..."

for i in {1..10}; do
  echo "Request $i:"
  curl -s http://localhost:8000/cache/status | \
    jq '.stats | {hit_rate, total_requests, cache_hits, avg_response_time_cached}'
  sleep 1
done
```

### Check Cache Memory Usage

```bash
# Redis info
redis-cli INFO memory

# Or through API
curl -s http://localhost:8000/cache/status | jq '.stats.memory_usage_mb'
```

### View Cached Entries

```bash
# List all cached keys
redis-cli KEYS "faq_cache:*"

# View specific entry
redis-cli GET "faq_cache:reset password"
```

---

## Use Cases

### 1. FAQ Chatbot

```python
# Frontend: Keep asking related questions
questions = [
    "How to reset password?",
    "Reset password please",
    "I forgot my password, what to do?",
]

for q in questions:
    response = requests.get("http://localhost:8000/ask",
                           params={"q": q})
    # All hit cache → 5ms response time
    print(f"Q: {q} → {response.json()['answer'][:50]}...")
```

### 2. Support Ticket Routing

```python
# Route common questions to FAQ (cache hit)
# Route uncommon questions to human (cache miss)

cache_status = requests.get("http://localhost:8000/cache/status").json()
hit_rate = cache_status["stats"]["hit_rate"]

if hit_rate > 80:
    print("✅ High cache hit rate - most questions are FAQs")
else:
    print("⚠️  Low cache hit rate - more manual support needed")
```

### 3. Performance Testing

```bash
# Test with Apache Bench
ab -n 1000 -c 10 \
  "http://localhost:8000/ask?q=How%20to%20reset%20password"

# Before cache: ~850ms per request
# After cache: ~5ms per request
# 170x speedup!
```

---

## Debugging

### Check if Query is Being Cached

```bash
# Look at logs during request
uvicorn app.main:app --reload

# You should see:
# ✅ Cache HIT for: 'How to reset password?'
# or
# ❌ Cache MISS for: 'How to reset password?'
```

### View Normalization Details

```bash
# Run demo to see normalization
python scripts/demo_cache.py

# You'll see:
# 'How to reset password?'
#   ✓ Normalized to: 'password reset'
```

### Test Cache Without API

```python
import asyncio
from app.cache.query_normalizer import QueryNormalizer
from app.cache.cache_layer import CacheManager
from app.cache.models import CacheEntry

async def test():
    cache = await CacheManager.create()
    normalizer = QueryNormalizer()

    # Normalize
    key = normalizer.normalize("How to reset password?")
    print(f"Cache key: {key}")

    # Store
    entry = CacheEntry(
        query_normalized=key,
        query_original="How to reset password?",
        answer="Click Forgot Password...",
        doc_ids=["faq_1"],
        confidence=0.95
    )
    await cache.set(key, entry)

    # Retrieve
    cached = await cache.get(key)
    print(f"Retrieved: {cached.answer}")

asyncio.run(test())
```

---

## Troubleshooting API Calls

### 404 Not Found

```
GET /ask → 404

Solution: Make sure app is running
  uvicorn app.main:app --reload
```

### 400 Bad Request

```
GET /ask (no ?q parameter) → 400

Solution: Add query parameter
  curl "http://localhost:8000/ask?q=your%20question"
```

### 500 Internal Server Error

```
GET /ask → 500

Check logs:
  - Is Redis running? docker ps
  - Is OPENAI_API_KEY set? echo $OPENAI_API_KEY
  - Are all dependencies installed? pip install -r requirements.txt
```

### Cache Not Working

```
# Cache disabled? Check pipeline_config.json:
  "cache": {"enabled": true}

# Redis unavailable? Check docker:
  docker logs support_rag_redis

# Check health endpoint:
  curl http://localhost:8000/cache/status
  # Should show "status": "healthy"
```

---

## Advanced Examples

### Batch Requests with Timing

```bash
#!/bin/bash

questions=(
  "How to reset password"
  "How to check order"
  "How to contact support"
  "reset password"  # Should hit cache
  "password reset"  # Should hit cache
)

for q in "${questions[@]}"; do
  echo "Q: $q"
  time curl -s "http://localhost:8000/ask?q=$(echo -n "$q" | jq -sRr @uri)" | jq '.answer[0:50]'
  echo
done
```

### Monitor Hit Rate Over Time

```python
import requests
import time
import json
from datetime import datetime

filename = "cache_metrics.jsonl"

while True:
    response = requests.get("http://localhost:8000/cache/status")
    data = response.json()
    timestamp = datetime.now().isoformat()

    metrics = {
        "timestamp": timestamp,
        "hit_rate": data["stats"]["hit_rate"],
        "total_requests": data["stats"]["total_requests"],
        "cache_hits": data["stats"]["cache_hits"],
        "memory_mb": data["stats"]["memory_usage_mb"]
    }

    with open(filename, "a") as f:
        f.write(json.dumps(metrics) + "\n")

    print(f"Hit rate: {metrics['hit_rate']:.1f}% - "
          f"Requests: {metrics['total_requests']} - "
          f"Memory: {metrics['memory_mb']:.1f}MB")

    time.sleep(60)
```

---

## Performance Benchmarks

### Cached Response
```
Response Time: 5-10ms
Memory: ~1KB per entry
Redis Overhead: <1ms
```

### Uncached Response
```
Response Time: 800-1000ms
Components: Classify → Retrieve → Rerank → Generate
```

### Hit Rate by Query Volume
```
10 queries/day:     ~20% hit rate
100 queries/day:    ~45% hit rate
1000 queries/day:   ~70% hit rate
10000 queries/day:  ~85% hit rate
```

---

**For more details, see [CACHE_GUIDE.md](CACHE_GUIDE.md)**
