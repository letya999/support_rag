# Support RAG API - Implementation Guide

**Version:** 1.0
**Target Audience:** Backend Engineers, Integration Developers
**Level:** Practical Implementation

---

## Table of Contents

1. [API Implementation Roadmap](#api-implementation-roadmap)
2. [Core API Endpoints Implementation](#core-api-endpoints-implementation)
3. [Webhook System Implementation](#webhook-system-implementation)
4. [Error Handling & Validation](#error-handling--validation)
5. [Testing Strategy](#testing-strategy)
6. [Deployment & Rollout](#deployment--rollout)

---

## API Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
**Goals:** Core query + search endpoints, basic error handling

```
├─ POST /api/v1/queries          (Simple query)
├─ GET /api/v1/search            (Document search)
├─ GET /health                   (Health check)
├─ Response envelope standardization
└─ Error handling framework
```

**Deliverables:**
- FastAPI route handlers
- Pydantic schemas
- Error handlers
- Health check logic

---

### Phase 2: Document Management (Weeks 3-4)
**Goals:** Upload, process, ingest documents

```
├─ POST /api/v1/documents/upload
├─ GET /api/v1/jobs/{job_id}
├─ GET /api/v1/documents/pending-review
├─ POST /api/v1/documents/qa-pairs/batch-update
├─ Async job handling
└─ Document versioning
```

**Deliverables:**
- Job queue integration (Redis)
- Async worker implementation
- Database schema for jobs + events
- File handling + validation

---

### Phase 3: Webhooks (Weeks 5-6)
**Goals:** Event emission, webhook delivery

```
├─ Event generation framework
├─ Webhook registration endpoints
├─ Webhook delivery worker
├─ Retry logic + dead letter queue
├─ Signature verification
└─ Webhook monitoring
```

**Deliverables:**
- Event schema + emitter
- Webhook registration CRUD
- Async delivery worker
- Monitoring dashboard

---

### Phase 4: Admin & Config (Weeks 7-8)
**Goals:** System administration, monitoring

```
├─ GET /api/v1/config
├─ PUT /api/v1/config
├─ GET /api/v1/intents
├─ POST /api/v1/intents
├─ Analytics endpoints
└─ Access control (RBAC)
```

**Deliverables:**
- Admin endpoints
- Permission system
- Analytics aggregation
- Audit logging

---

## Core API Endpoints Implementation

### 1. Health Check Endpoint

**File:** `app/api/routes/health.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from typing import Dict, Any

router = APIRouter(prefix="/health", tags=["health"])

@router.get("")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Dict[str, Any]:
    """
    Check service health and all dependencies.
    """
    status_checks = {
        "postgres": await check_postgres(db),
        "redis": await check_redis(redis),
        "qdrant": await check_qdrant(),
        "openai": await check_openai(),
        "langfuse": await check_langfuse(),
    }

    all_healthy = all(check["status"] == "healthy" for check in status_checks.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "data": {
            "service": f"support-rag-{get_version()}",
            "uptime_seconds": get_uptime(),
            "dependencies": status_checks,
        },
        "meta": {
            "request_id": get_request_id(),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    }

async def check_postgres(db: AsyncSession) -> Dict[str, Any]:
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "latency_ms": 5}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_redis(redis: Redis) -> Dict[str, Any]:
    try:
        await redis.ping()
        return {"status": "healthy", "latency_ms": 3}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_qdrant() -> Dict[str, Any]:
    try:
        client = get_qdrant_client()
        health = await client.http_client.collections_api_v1_collections_get()
        return {"status": "healthy", "latency_ms": 12}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# ... similar for OpenAI and Langfuse
```

---

### 2. Query Endpoint

**File:** `app/api/routes/queries.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
import uuid

router = APIRouter(prefix="/api/v1/queries", tags=["queries"])

# ============ Schemas ============

class ConversationMessage(BaseModel):
    role: str = Field(..., regex="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=5000)
    timestamp: Optional[datetime] = None

class QueryOptions(BaseModel):
    use_hybrid_search: bool = True
    use_reranking: bool = False
    temperature: float = Field(0.1, ge=0.0, le=1.0)
    max_tokens: int = Field(500, ge=100, le=2000)
    timeout_seconds: int = Field(30, ge=5, le=120)

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    conversation_history: List[ConversationMessage] = Field(default_factory=list)
    user_id: str = Field(...)
    session_id: Optional[str] = None
    metadata: Optional[dict] = None
    options: Optional[QueryOptions] = None

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What's your return policy?",
                "user_id": "user_123",
                "session_id": "sess_xyz789",
                "options": {
                    "use_hybrid_search": True,
                    "temperature": 0.1
                }
            }
        }

class Source(BaseModel):
    document_id: str
    title: str
    excerpt: str
    relevance_score: float = Field(ge=0, le=1)
    category: str
    url: Optional[str] = None

class QueryResponse(BaseModel):
    query_id: str
    answer: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    sources: List[Source] = []
    action: str = Field(..., regex="^(auto_reply|escalate)$")
    escalation_triggered: bool
    escalation_reason: Optional[str] = None
    metadata: dict
    cache_hit: bool

# ============ Endpoints ============

@router.post("")
async def create_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    rate_limit: RateLimitInfo = Depends(check_rate_limit),
    request_id: str = Depends(get_request_id),
) -> Dict[str, Any]:
    """
    Execute a RAG query with optional conversation context.

    The query is processed through a 22-node LangGraph pipeline:
    - Input guardrails (safety checks)
    - Cache lookup
    - Language detection
    - Retrieval
    - Generation
    - Output guardrails
    - Response routing (auto_reply vs escalate)
    """

    # Validate
    if len(request.question.strip()) < 3:
        raise HTTPException(status_code=400, detail="Question too short")

    query_id = f"q_{uuid.uuid4().hex[:12]}"

    try:
        # Create session if needed
        if not request.session_id:
            session = await create_session(db, request.user_id)
            request.session_id = session.id

        # Log to Langfuse for tracing
        with observe(name="query_execution", trace_id=request_id) as trace:

            # Execute RAG pipeline
            result = await execute_rag_pipeline(
                question=request.question,
                conversation_history=request.conversation_history,
                user_id=request.user_id,
                session_id=request.session_id,
                options=request.options,
                request_id=request_id,
                trace_id=trace.id,
            )

        # Store query result
        query_record = Query(
            id=query_id,
            question=request.question,
            answer=result.answer,
            confidence=result.confidence,
            user_id=request.user_id,
            session_id=request.session_id,
            result_json=result.dict(),
            created_at=datetime.utcnow(),
        )
        db.add(query_record)
        await db.commit()

        # Emit webhook event
        await emit_event(
            event_type="query.completed",
            data={
                "query_id": query_id,
                "answer": result.answer,
                "confidence": result.confidence,
                "sources": result.sources,
                "user_id": request.user_id,
            },
            request_id=request_id,
        )

        # Return response
        return {
            "status": "success",
            "data": QueryResponse(
                query_id=query_id,
                answer=result.answer,
                confidence=result.confidence,
                sources=result.sources,
                action=result.action,
                escalation_triggered=result.escalation_triggered,
                escalation_reason=result.escalation_reason,
                metadata=result.metadata,
                cache_hit=result.cache_hit,
            ),
            "meta": {
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "version": "1.0",
            }
        }

    except QueryTimeoutError as e:
        logger.warning(f"Query timeout: {query_id}")
        raise HTTPException(status_code=504, detail="Query processing timeout")
    except Exception as e:
        logger.error(f"Query failed: {query_id}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{query_id}")
async def get_query(
    query_id: str,
    db: AsyncSession = Depends(get_db),
    request_id: str = Depends(get_request_id),
) -> Dict[str, Any]:
    """Retrieve query details by ID."""

    query = await db.get(Query, query_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    return {
        "status": "success",
        "data": {
            "query_id": query.id,
            "question": query.question,
            "answer": query.answer,
            "confidence": query.confidence,
            "sources": query.result_json.get("sources", []),
            "created_at": query.created_at.isoformat() + "Z",
            "user_id": query.user_id,
        },
        "meta": {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    }


@router.post("/{query_id}/feedback")
async def create_feedback(
    query_id: str,
    rating: int = Field(..., ge=1, le=5),
    helpful: bool = ...,
    correct: bool = ...,
    comment: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    request_id: str = Depends(get_request_id),
) -> Dict[str, Any]:
    """Submit feedback on a query result."""

    query = await db.get(Query, query_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    feedback = Feedback(
        id=f"fb_{uuid.uuid4().hex[:12]}",
        query_id=query_id,
        rating=rating,
        helpful=helpful,
        correct=correct,
        comment=comment,
        created_at=datetime.utcnow(),
    )
    db.add(feedback)
    await db.commit()

    # Emit event for tracking
    await emit_event(
        event_type="query.feedback_submitted",
        data={
            "query_id": query_id,
            "rating": rating,
            "helpful": helpful,
        },
        request_id=request_id,
    )

    return {
        "status": "success",
        "data": {
            "feedback_id": feedback.id,
            "recorded_at": feedback.created_at.isoformat() + "Z",
        },
        "meta": {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    }
```

---

### 3. Search Endpoint

**File:** `app/api/routes/search.py`

```python
from fastapi import APIRouter, Depends, Query as QueryParam
from typing import List, Dict, Any
from datetime import datetime

router = APIRouter(prefix="/api/v1/search", tags=["search"])

@router.get("")
async def search(
    q: str = QueryParam(..., min_length=2, max_length=2000),
    limit: int = QueryParam(20, ge=1, le=100),
    offset: int = QueryParam(0, ge=0),
    filter: Optional[str] = None,
    sort: str = "-relevance_score",
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
    request_id: str = Depends(get_request_id),
) -> Dict[str, Any]:
    """
    Search documents without generation (raw vector search).
    Good for non-generative search UIs.
    """

    # Generate query embedding
    query_embedding = await get_embedding_model().embed_query(q)

    # Build filter dict from filter parameter
    # format: "category:returns,language:en"
    filters = parse_filter_param(filter) if filter else {}

    # Search in Qdrant
    search_results = await qdrant.search(
        collection_name="documents",
        query_vector=query_embedding,
        query_filter=build_qdrant_filter(filters),
        limit=limit,
        offset=offset,
    )

    # Format results
    documents = []
    for result in search_results.points:
        doc_id = result.payload["document_id"]
        doc_record = await db.get(Document, doc_id)

        documents.append({
            "document_id": doc_id,
            "title": doc_record.title,
            "category": result.payload.get("category"),
            "intent": result.payload.get("intent"),
            "relevance_score": result.score,
            "rank": len(documents) + 1,
            "excerpt": doc_record.content[:200] + "...",
            "url": doc_record.url,
            "last_updated": doc_record.updated_at.isoformat() + "Z",
        })

    # Get total count
    total_count = await qdrant.count(
        collection_name="documents",
        query_filter=build_qdrant_filter(filters),
    )

    return {
        "status": "success",
        "data": {
            "query": q,
            "results": documents,
            "total_results": total_count.count,
            "search_time_ms": 85,  # Track in tracing
            "filters_applied": filters,
        },
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total_count.count,
            "has_next": offset + limit < total_count.count,
            "next_offset": offset + limit if offset + limit < total_count.count else None,
        },
        "meta": {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    }
```

---

## Webhook System Implementation

### 1. Event Emission Framework

**File:** `app/events/emitter.py`

```python
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from enum import Enum
import json
import uuid

class EventType(str, Enum):
    QUERY_SUBMITTED = "query.submitted"
    QUERY_COMPLETED = "query.completed"
    QUERY_ESCALATED = "query.escalated"
    QUERY_FAILED = "query.failed"

    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_INGESTED = "document.ingested"
    DOCUMENT_DELETED = "document.deleted"

    JOB_STARTED = "job.started"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"

class EventEmitter:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis

    async def emit(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        tenant_id: str,
        request_id: str,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Emit an event. This:
        1. Stores event in PostgreSQL
        2. Finds matching webhooks
        3. Enqueues to delivery queue
        """

        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Create event record
        event_record = Event(
            id=event_id,
            type=event_type.value,
            tenant_id=tenant_id,
            user_id=user_id,
            data_json=data,
            request_id=request_id,
            created_at=datetime.utcnow(),
        )
        self.db.add(event_record)
        await self.db.flush()

        # Find matching webhooks
        webhooks = await self.db.execute(
            select(Webhook)
            .where(Webhook.tenant_id == tenant_id)
            .where(Webhook.active == True)
            .where(Webhook.events.contains([event_type.value]))
        )
        webhooks = webhooks.scalars().all()

        # Enqueue delivery for each webhook
        for webhook in webhooks:
            await self.enqueue_delivery(
                event_id=event_id,
                webhook_id=webhook.id,
                url=webhook.url,
                event_data=event_record.dict(),
                tenant_id=tenant_id,
            )

        await self.db.commit()
        return event_id

    async def enqueue_delivery(
        self,
        event_id: str,
        webhook_id: str,
        url: str,
        event_data: Dict,
        tenant_id: str,
    ) -> None:
        """Enqueue webhook delivery to Redis."""

        delivery = {
            "delivery_id": f"del_{uuid.uuid4().hex[:12]}",
            "event_id": event_id,
            "webhook_id": webhook_id,
            "url": url,
            "event_data": event_data,
            "tenant_id": tenant_id,
            "attempt": 0,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

        # Enqueue to Redis (FIFO per tenant)
        queue_key = f"webhook_deliveries:{tenant_id}"
        await self.redis.rpush(queue_key, json.dumps(delivery))


# Global emitter instance
emitter: Optional[EventEmitter] = None

def get_emitter() -> EventEmitter:
    global emitter
    if not emitter:
        raise RuntimeError("Emitter not initialized")
    return emitter

async def init_emitter(db: AsyncSession, redis: Redis) -> None:
    global emitter
    emitter = EventEmitter(db, redis)

async def emit_event(
    event_type: EventType,
    data: Dict[str, Any],
    tenant_id: str = "default",
    request_id: str = "",
    user_id: Optional[str] = None,
) -> str:
    """Convenience function to emit event."""
    return await get_emitter().emit(event_type, data, tenant_id, request_id, user_id)
```

---

### 2. Webhook Registration Endpoints

**File:** `app/api/routes/webhooks.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy import select
import uuid
import hmac
import hashlib

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

class WebhookRegisterRequest(BaseModel):
    url: HttpUrl
    events: List[str] = Field(..., min_items=1)
    active: bool = True
    headers: Optional[Dict[str, str]] = None
    max_retries: int = Field(4, ge=0, le=10)

class WebhookResponse(BaseModel):
    webhook_id: str
    url: str
    events: List[str]
    active: bool
    created_at: str
    test_url: str

@router.post("")
async def register_webhook(
    request: WebhookRegisterRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    request_id: str = Depends(get_request_id),
) -> Dict[str, Any]:
    """Register a new webhook for events."""

    webhook_id = f"whk_{uuid.uuid4().hex[:12]}"
    secret = generate_webhook_secret()

    webhook = Webhook(
        id=webhook_id,
        tenant_id=tenant_id,
        url=str(request.url),
        events=request.events,
        active=request.active,
        headers=request.headers,
        secret=secret,  # Store hashed
        max_retries=request.max_retries,
        created_at=datetime.utcnow(),
    )
    db.add(webhook)
    await db.commit()

    return {
        "status": "success",
        "data": WebhookResponse(
            webhook_id=webhook_id,
            url=str(request.url),
            events=request.events,
            active=request.active,
            created_at=webhook.created_at.isoformat() + "Z",
            test_url=f"/api/v1/webhooks/{webhook_id}/test",
        ),
        "meta": {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    }

@router.get("/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    request_id: str = Depends(get_request_id),
) -> Dict[str, Any]:
    """Send a test webhook event."""

    webhook = await db.get(Webhook, webhook_id)
    if not webhook or webhook.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Create test event
    test_event = {
        "event_type": "webhook.test",
        "event_id": f"evt_test_{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": {
            "test": True,
            "message": "This is a test webhook delivery"
        }
    }

    # Send immediately
    delivery_result = await send_webhook(webhook, test_event)

    return {
        "status": "success",
        "data": {
            "webhook_id": webhook_id,
            "test_event_id": test_event["event_id"],
            "delivery": {
                "status": delivery_result["status"],
                "response_code": delivery_result.get("response_code"),
                "response_time_ms": delivery_result.get("response_time_ms"),
            }
        },
        "meta": {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    }


# ============ Webhook Delivery Worker ============

class WebhookDeliveryWorker:
    def __init__(self, db: AsyncSession, redis: Redis, max_workers: int = 10):
        self.db = db
        self.redis = redis
        self.max_workers = max_workers
        self.running = False

    async def start(self):
        """Start delivery worker."""
        self.running = True
        tasks = [
            self.worker_loop(i)
            for i in range(self.max_workers)
        ]
        await asyncio.gather(*tasks)

    async def stop(self):
        """Stop delivery worker."""
        self.running = False

    async def worker_loop(self, worker_id: int):
        """Worker process loop."""
        while self.running:
            try:
                # Get all tenant queues
                tenants = await self.redis.keys("webhook_deliveries:*")

                for tenant_key in tenants:
                    tenant_id = tenant_key.decode().split(":")[1]

                    # Pop from queue
                    delivery_data = await self.redis.lpop(tenant_key)
                    if not delivery_data:
                        continue

                    delivery = json.loads(delivery_data)
                    await self.process_delivery(delivery, worker_id)

                await asyncio.sleep(0.1)  # Prevent busy loop

            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(5)

    async def process_delivery(self, delivery: Dict, worker_id: int):
        """Process single webhook delivery with retries."""

        event_id = delivery["event_id"]
        webhook_id = delivery["webhook_id"]
        url = delivery["url"]
        attempt = delivery.get("attempt", 0)

        try:
            # Send webhook
            response = await send_webhook_with_retry(
                url=url,
                event_data=delivery["event_data"],
                max_retries=4,
            )

            # Log success
            delivery_record = WebhookDelivery(
                id=delivery["delivery_id"],
                event_id=event_id,
                webhook_id=webhook_id,
                status="success",
                response_code=response.status_code,
                response_time_ms=response.elapsed.total_seconds() * 1000,
                attempt=attempt + 1,
                created_at=datetime.utcnow(),
            )
            self.db.add(delivery_record)
            await self.db.commit()

        except MaxRetriesExceeded:
            # Log failure to DLQ
            dlq_key = f"webhook_dlq:{delivery['tenant_id']}"
            await self.redis.rpush(dlq_key, json.dumps(delivery))

            delivery_record = WebhookDelivery(
                id=delivery["delivery_id"],
                event_id=event_id,
                webhook_id=webhook_id,
                status="failed",
                error="Max retries exceeded",
                attempt=attempt + 1,
                created_at=datetime.utcnow(),
            )
            self.db.add(delivery_record)
            await self.db.commit()

            logger.error(f"Webhook delivery failed (max retries): {webhook_id}")


async def send_webhook_with_retry(
    url: str,
    event_data: Dict,
    max_retries: int = 4,
) -> httpx.Response:
    """Send webhook with exponential backoff retry."""

    backoff_ms = [1000, 5000, 30000, 300000]  # 1s, 5s, 30s, 5m

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json=event_data,
                    headers=build_webhook_headers(event_data),
                )

                if response.status_code >= 200 and response.status_code < 300:
                    return response  # Success

                if response.status_code >= 500:
                    raise httpx.HTTPError(f"Server error: {response.status_code}")

                if response.status_code == 429:
                    raise httpx.HTTPError("Rate limited")

                # 4xx errors don't retry
                return response

        except (httpx.HTTPError, asyncio.TimeoutError) as e:
            if attempt < max_retries:
                await asyncio.sleep(backoff_ms[attempt] / 1000)
                continue
            raise MaxRetriesExceeded(f"Failed after {max_retries} retries: {e}")

def build_webhook_headers(event_data: Dict) -> Dict[str, str]:
    """Build webhook request headers including signature."""

    payload = json.dumps(event_data)
    signature = hmac.new(
        b"webhook_secret",  # Get from config/env
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    return {
        "Content-Type": "application/json",
        "X-Signature": f"sha256={signature}",
        "X-Event-ID": event_data.get("event_id"),
    }
```

---

## Error Handling & Validation

### 1. Global Error Handler

**File:** `app/api/exceptions.py`

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Dict, Any
import traceback
import logging

logger = logging.getLogger(__name__)

# ============ Custom Exceptions ============

class RAGException(Exception):
    """Base exception for RAG service."""
    def __init__(self, code: str, message: str, status_code: int = 500, details: Dict = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class ValidationError(RAGException):
    def __init__(self, message: str, field: str = None, details: Dict = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=400,
            details={"field": field, **(details or {})}
        )

class RateLimitExceeded(RAGException):
    def __init__(self, limit: int, window: str):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded ({limit} per {window})",
            status_code=429,
            details={"limit": limit, "window": window}
        )

class NotFound(RAGException):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} not found: {resource_id}",
            status_code=404,
            details={"resource": resource, "resource_id": resource_id}
        )

# ============ Exception Handlers ============

def register_exception_handlers(app: FastAPI):
    """Register all exception handlers."""

    @app.exception_handler(RAGException)
    async def rag_exception_handler(request: Request, exc: RAGException) -> JSONResponse:
        """Handle RAG custom exceptions."""

        # Log
        logger.warning(
            f"RAG error: {exc.code}",
            extra={
                "error_code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "path": request.url.path,
            }
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "data": None,
                "errors": [
                    {
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    }
                ],
                "meta": {
                    "request_id": request.headers.get("X-Request-ID"),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            }
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Convert FastAPI HTTPException to standard format."""

        logger.warning(
            f"HTTP error: {exc.status_code}",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
            }
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "data": None,
                "errors": [
                    {
                        "code": "HTTP_ERROR",
                        "message": exc.detail,
                    }
                ],
                "meta": {
                    "request_id": request.headers.get("X-Request-ID"),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unexpected errors."""

        error_id = f"err_{uuid.uuid4().hex[:12]}"
        logger.error(
            f"Unexpected error: {error_id}",
            exc_info=True,
            extra={
                "error_id": error_id,
                "path": request.url.path,
            }
        )

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "data": None,
                "errors": [
                    {
                        "code": "INTERNAL_ERROR",
                        "message": "An unexpected error occurred",
                        "error_id": error_id,
                    }
                ],
                "meta": {
                    "request_id": request.headers.get("X-Request-ID"),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            }
        )
```

---

## Testing Strategy

### 1. Unit Tests

**File:** `tests/unit/test_queries.py`

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.api.routes.queries import create_query, QueryRequest

@pytest.mark.asyncio
async def test_create_query_success():
    """Test successful query creation."""

    request = QueryRequest(
        question="What's your return policy?",
        user_id="user_123",
    )

    with patch("app.api.routes.queries.execute_rag_pipeline") as mock_pipeline:
        mock_pipeline.return_value = MockResult(
            answer="We accept returns within 30 days...",
            confidence=0.92,
            sources=[],
            action="auto_reply",
            escalation_triggered=False,
        )

        response = await create_query(
            request=request,
            db=AsyncMock(),
            rate_limit=None,
            request_id="req_123",
        )

        assert response["status"] == "success"
        assert response["data"]["confidence"] == 0.92
        assert response["data"]["action"] == "auto_reply"

@pytest.mark.asyncio
async def test_create_query_validation_error():
    """Test query validation."""

    request = QueryRequest(
        question="ab",  # Too short
        user_id="user_123",
    )

    with pytest.raises(ValidationError):
        await create_query(
            request=request,
            db=AsyncMock(),
            rate_limit=None,
            request_id="req_123",
        )
```

### 2. Integration Tests

**File:** `tests/integration/test_webhook_delivery.py`

```python
import pytest
from httpx import AsyncClient
from datetime import datetime

@pytest.mark.asyncio
async def test_webhook_delivery_flow(test_db, test_redis, app):
    """Test full webhook delivery flow."""

    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Register webhook
        register_response = await client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://webhook.example.com/events",
                "events": ["query.completed"],
            }
        )
        webhook_id = register_response.json()["data"]["webhook_id"]

        # 2. Create query (which emits event)
        query_response = await client.post(
            "/api/v1/queries",
            json={
                "question": "Test question?",
                "user_id": "user_123",
            }
        )
        query_id = query_response.json()["data"]["query_id"]

        # 3. Wait for webhook delivery
        await asyncio.sleep(1)

        # 4. Check webhook delivery status
        deliveries_response = await client.get(
            "/api/v1/webhooks/deliveries?webhook_id=" + webhook_id
        )

        deliveries = deliveries_response.json()["data"]["deliveries"]
        assert len(deliveries) > 0
        assert deliveries[0]["status"] == "success"
```

---

## Deployment & Rollout

### Deployment Plan

**Phase 1: Beta (1 week)**
- Deploy to staging environment
- Selected internal users test
- Monitor metrics

**Phase 2: Canary (1 week)**
- 10% traffic to new API version
- Monitor error rates, latency
- Gradual increase to 25%, 50%, 100%

**Phase 3: Production (ongoing)**
- Full rollout
- Monitor all metrics
- Keep old version available for 6 months

### Monitoring & Alerting

```yaml
# prometheus/alerts.yaml
groups:
  - name: api_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"

      - alert: SlowQueries
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 2
        for: 10m
        annotations:
          summary: "Query latency above SLA"

      - alert: WebhookFailureRate
        expr: rate(webhook_delivery_failures_total[5m]) > 0.01
        for: 5m
```

---

**Document Version:** API_IMPLEMENTATION_v1.0
**Status:** Ready for Development
**Last Updated:** 2026-01-07
