# Support RAG - Integration Architecture & Webhooks Design

**Version:** 1.0
**Level:** Staff Engineer / Principal Architect
**Date:** 2026-01-07

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Webhook Architecture](#webhook-architecture)
3. [Event-Driven Workflow Scenarios](#event-driven-workflow-scenarios)
4. [Integration Patterns](#integration-patterns)
5. [Third-Party Integration Guide](#third-party-integration-guide)
6. [Scalability & Performance](#scalability--performance)
7. [Observability & Monitoring](#observability--monitoring)
8. [Security in Integrations](#security-in-integrations)

---

## Executive Summary

### Why This Architecture?

The Support RAG service is designed as an **event-driven, composable system** where:

1. **Core API** handles **synchronous** operations (queries, document retrieval)
2. **Webhooks** enable **asynchronous** notification of long-running processes
3. **Integration layer** allows third-party systems to:
   - React to RAG events in real-time
   - Trigger RAG workflows from external systems
   - Build complex multi-service orchestrations

### Key Benefits

✅ **Decoupling:** Third-party systems don't need to poll or maintain tight coupling
✅ **Real-time:** Events propagate immediately when they occur
✅ **Resilience:** Webhook retry logic + event log ensures no lost events
✅ **Observability:** Full audit trail of all system interactions
✅ **Scalability:** Event-driven architecture scales horizontally
✅ **Multi-tenant:** Webhooks scoped to individual tenants/organizations

---

## Webhook Architecture

### 1. Event Production

The service generates events across **4 lifecycle stages**:

```
┌─────────────────────────────────────────────────────────┐
│                  RAG SERVICE EVENT FLOW                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  [INPUT]                                               │
│    ↓                                                    │
│  ┌─────────────────────────────────────────────┐      │
│  │ 1. QUERY EVENTS                             │      │
│  │  - query.submitted      (async trigger)    │      │
│  │  - query.completed      (result ready)     │      │
│  │  - query.escalated      (human needed)     │      │
│  │  - query.failed         (error occurred)   │      │
│  └─────────────────────────────────────────────┘      │
│    ↓                                                    │
│  ┌─────────────────────────────────────────────┐      │
│  │ 2. DOCUMENT EVENTS                          │      │
│  │  - document.uploaded    (ingestion started)│      │
│  │  - document.processing  (QA extraction)    │      │
│  │  - document.qa_reviewed (metadata ok)      │      │
│  │  - document.ingested    (indexed+ready)    │      │
│  │  - document.failed      (error occurred)   │      │
│  │  - document.deleted     (archived)         │      │
│  └─────────────────────────────────────────────┘      │
│    ↓                                                    │
│  ┌─────────────────────────────────────────────┐      │
│  │ 3. JOB LIFECYCLE EVENTS                     │      │
│  │  - job.started          (async work begin) │      │
│  │  - job.progress         (% complete)       │      │
│  │  - job.completed        (success)          │      │
│  │  - job.failed           (terminal error)   │      │
│  └─────────────────────────────────────────────┘      │
│    ↓                                                    │
│  ┌─────────────────────────────────────────────┐      │
│  │ 4. SYSTEM EVENTS                            │      │
│  │  - system.health_changed   (outage/recovery)      │
│  │  - system.config_updated   (config reload) │      │
│  │  - system.quota_exceeded   (rate limit)    │      │
│  └─────────────────────────────────────────────┘      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 2. Event Storage & Delivery

```
┌──────────────────────────────────────────────────────┐
│              WEBHOOK DELIVERY PIPELINE                │
├──────────────────────────────────────────────────────┤
│                                                      │
│  [Event Generated]                                 │
│    ↓                                                │
│  ┌────────────────────────────────────┐            │
│  │ 1. Event Persistence Layer         │            │
│  │    PostgreSQL `events` table       │            │
│  │    - Immutable event log           │            │
│  │    - Soft-delete capable           │            │
│  │    - Indexed by: event_type,       │            │
│  │      created_at, tenant_id         │            │
│  └────────────────────────────────────┘            │
│    ↓                                                │
│  ┌────────────────────────────────────┐            │
│  │ 2. Webhook Matching                │            │
│  │    - Find subscribed webhooks      │            │
│  │    - Filter by event_type          │            │
│  │    - Filter by tenant_id           │            │
│  └────────────────────────────────────┘            │
│    ↓                                                │
│  ┌────────────────────────────────────┐            │
│  │ 3. Queue Enqueuing                 │            │
│  │    Redis Queue:                    │            │
│  │    - webhook_deliveries:{tenant}   │            │
│  │    - Priority queue (high/normal)  │            │
│  └────────────────────────────────────┘            │
│    ↓                                                │
│  ┌────────────────────────────────────┐            │
│  │ 4. Async Delivery Worker           │            │
│  │    - Pull from queue               │            │
│  │    - HTTP POST with retries        │            │
│  │    - Track delivery status         │            │
│  │    - Log failures                  │            │
│  └────────────────────────────────────┘            │
│    ↓                                                │
│  [Webhook URL]                                     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 3. Event Payload Structure

Every event follows this **canonical format**:

```json
{
  "event_type": "query.completed",
  "event_id": "evt_abc123xyz",
  "event_version": "1.0",

  "timestamp": "2026-01-07T10:16:00.000Z",
  "occurred_at": "2026-01-07T10:15:50.000Z",

  "source": {
    "service": "support-rag",
    "version": "1.0.0",
    "region": "us-east-1"
  },

  "tenant_id": "tenant_123",
  "actor": {
    "type": "user|system|api",
    "id": "user_123|system|api_key_abc"
  },

  "data": {
    "query_id": "q_abc123",
    "question": "What's your return policy?",
    "answer": "We accept returns within 30 days...",
    "confidence": 0.92,
    "user_id": "user_123",
    "session_id": "sess_xyz789"
  },

  "metadata": {
    "request_id": "req_abc123xyz",
    "trace_id": "trace_xyz789",
    "parent_event_id": null,
    "related_events": ["evt_def456"]
  },

  "context": {
    "environment": "production",
    "api_version": "v1",
    "timezone": "UTC"
  }
}
```

---

## Event-Driven Workflow Scenarios

### Scenario 1: Real-Time Query Escalation → CRM Integration

```
┌─────────────────────────────────────────────────────────┐
│                                                          │
│  USER ASKS QUESTION                                    │
│  "I want to return a damaged item"                     │
│    ↓                                                    │
│  RAG SYSTEM DETECTS                                    │
│  - Low confidence (0.3)                                │
│  - Requires human involvement                          │
│    ↓                                                    │
│  EMIT EVENT: query.escalated                           │
│  ┌──────────────────────────────────┐                 │
│  │ {                                 │                 │
│  │   "event_type": "query.escalated" │                 │
│  │   "query_id": "q_abc",            │                 │
│  │   "escalation_reason": "...",     │                 │
│  │   "escalation_category": "damage_claim",           │
│  │   "user_id": "user_123"           │                 │
│  │ }                                 │                 │
│  └──────────────────────────────────┘                 │
│    ↓                                                    │
│  WEBHOOK DELIVERY (your CRM)                          │
│  POST https://crm.example.com/webhooks/supportrag     │
│    ↓                                                    │
│  CRM SYSTEM RECEIVES EVENT                            │
│  - Creates ticket in Zendesk/Intercom                 │
│  - Assigns to damage claim team                       │
│  - Notifies user: "Escalating to specialist..."       │
│    ↓                                                    │
│  SYNC BACK (via your API)                             │
│  POST /api/v1/queries/{query_id}/feedback             │
│  { "escalation_status": "assigned_to_agent_xyz" }     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Scenario 2: Document Ingestion with Quality Gate

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│  UPLOAD FAQ DOCUMENT                               │
│  POST /api/v1/documents/upload                      │
│  faq.pdf (450KB)                                    │
│    ↓                                                │
│  JOB CREATED: job_upload_001                        │
│  ├─ Status: processing                             │
│  └─ Emit: document.uploaded                        │
│    ↓                                                │
│  WEBHOOK → Your Quality Assurance System            │
│  "New document ready for review"                   │
│    ↓                                                │
│  QA SYSTEM RETRIEVES EXTRACTED Q&A                 │
│  GET /api/v1/documents/pending-review?job_id=...  │
│    ↓                                                │
│  QA TEAM REVIEWS IN YOUR DASHBOARD                │
│  - Corrects metadata                              │
│  - Approves/rejects Q&A pairs                      │
│    ↓                                                │
│  QA SYSTEM CALLS BACK:                             │
│  POST /api/v1/documents/qa-pairs/batch-update      │
│  { "updates": [...], "action": "approve_and_ingest" }
│    ↓                                                │
│  JOB STATUS UPDATED: indexing                       │
│  └─ Emit: document.qa_reviewed                     │
│    ↓                                                │
│  WEBHOOK → Your Analytics System                   │
│  "Document moved to indexing stage"               │
│    ↓                                                │
│  INDEXING COMPLETES                                │
│  ├─ Vector embeddings created                      │
│  ├─ PostgreSQL indexed                             │
│  └─ Emit: document.ingested                        │
│    ↓                                                │
│  WEBHOOK → Your Dashboard                          │
│  "FAQ document live! 42 Q&A pairs indexed"        │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Scenario 3: Batch Evaluation Workflow

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  QUALITY TEAM INITIATES EVALUATION                     │
│  POST /api/v1/evaluation/ragas                         │
│  { "dataset_id": "dataset_001", "metrics": [...] }    │
│    ↓                                                    │
│  JOB CREATED & QUEUED                                 │
│  └─ Emit: job.started                                 │
│    ↓ [Every 5 minutes]                                │
│  EMIT: job.progress                                   │
│  { "progress": 0.35, "eta_seconds": 45 }             │
│    ↓                                                    │
│  WEBHOOK → Your Monitoring System                     │
│  Updates progress bar in dashboard                    │
│    ↓                                                    │
│  EVALUATION COMPLETES                                 │
│  └─ Emit: job.completed                               │
│    ↓                                                    │
│  WEBHOOK → Your Analytics System                      │
│  { "metrics": { "context_precision": 0.81, ... } }   │
│    ↓                                                    │
│  YOUR SYSTEM:                                         │
│  - Stores results in data warehouse                   │
│  - Generates comparison charts                        │
│  - Sends Slack notification to team                   │
│  - Alerts if metrics dropped >5%                      │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## Integration Patterns

### Pattern 1: Fire-and-Forget (Async Notification)

**Use Case:** Quick notifications, non-critical updates

```python
# RAG Service sends webhook
POST /webhooks/myapp
{
  "event_type": "query.completed",
  "data": { "query_id": "...", "answer": "..." }
}

# Your system responds immediately
HTTP 200 OK
{
  "status": "received"
}

# Your system processes later (background worker)
# No guaranteed delivery, but good for high-volume events
```

**Best For:**
- Analytics tracking
- Dashboard updates
- Non-blocking notifications

---

### Pattern 2: Request-Reply (RPC-style)

**Use Case:** Critical workflow requiring immediate action

```python
# Your system calls RAG synchronously
POST /api/v1/queries
{
  "question": "...",
  "timeout_seconds": 30
}

# RAG waits and returns answer
HTTP 200 OK (within 30s)
{
  "answer": "...",
  "sources": [...]
}

# Your system immediately processes result
result = response.json()
if result['confidence'] < 0.5:
    escalate_to_human()
```

**Best For:**
- Real-time chat
- Synchronous workflows
- Must-have-answer scenarios

---

### Pattern 3: Event Sourcing (Event Log Replay)

**Use Case:** Audit trail, compliance, debugging

```
Your System Architecture:
┌──────────────────────────────────────┐
│  RAG Event Log                       │
│  (PostgreSQL)                        │
│  ├─ query.submitted                 │
│  ├─ query.completed                 │
│  ├─ document.ingested               │
│  └─ ... (immutable history)         │
└──────────────────────────────────────┘
  ↓
Your Event Processor reads events:
  1. Tails event log
  2. Projects to read models
  3. Updates analytics DB
  4. Rebuilds cache
  5. Handles retries via event replay
```

**API to support this:**

```
# Query event log
GET /api/v1/events?since=2026-01-07T00:00:00Z&limit=1000&event_types=query.*

# Response includes cursor for pagination
{
  "events": [...],
  "pagination": {
    "cursor": "evt_cursor_xyz789",
    "has_next": true
  }
}
```

---

### Pattern 4: CQRS (Command Query Responsibility Segregation)

**Use Case:** Complex domains with read/write separation

```
┌─────────────────────────────────┐
│  WRITE SIDE (Your System)       │
│  POST /api/v1/documents/upload  │
│  → Stores in staging area       │
│  → Emits document.uploaded      │
└─────────────────────────────────┘
          ↓
  [Webhook: document.qa_reviewed]
          ↓
┌─────────────────────────────────┐
│  PROJECTION (Read Model)        │
│  Your system builds:            │
│  - Document dashboard           │
│  - Search index                 │
│  - Analytics views              │
└─────────────────────────────────┘
```

---

## Third-Party Integration Guide

### Integration Levels

#### Level 1: Query Integration (Easiest)

**What it does:** Integrates RAG querying into your app

```python
from supportrag import Client

client = Client(api_key="sk_live_xyz")

@app.post("/chat")
def chat(message: str):
    response = client.queries.create(
        question=message,
        user_id=current_user.id
    )
    return {
        "answer": response.answer,
        "sources": response.sources,
        "confidence": response.confidence
    }
```

**Integration Time:** 1-2 hours
**Complexity:** Low

---

#### Level 2: Document Management Integration

**What it does:** Manages documents through your UI

```python
@app.post("/manage-docs/upload")
def upload_docs(files: List[UploadFile]):
    job = client.documents.upload(
        files=files,
        metadata={"category": "faq"}
    )

    # Your system polls or uses webhook
    client.webhooks.register(
        url="https://yourapp.example.com/webhooks/doc-updates",
        events=["document.ingested", "document.failed"]
    )

    return {"job_id": job.job_id}

@app.post("/webhooks/doc-updates")
def handle_doc_webhook(event: dict):
    if event['event_type'] == 'document.ingested':
        # Update your UI
        notify_user(f"Document ready! {event['data']['qa_ingested']} Q&As")
```

**Integration Time:** 4-8 hours
**Complexity:** Medium

---

#### Level 3: Full Event-Driven Integration

**What it does:** Deep integration with webhooks + event streaming

```python
# Register multiple webhook subscriptions
webhooks = [
    {
        "url": "https://analytics.example.com/webhooks/rag",
        "events": ["query.completed", "query.escalated"]
    },
    {
        "url": "https://crm.example.com/webhooks/rag",
        "events": ["query.escalated"]
    },
    {
        "url": "https://warehouse.example.com/webhooks/rag",
        "events": ["*"]  # All events
    }
]

for webhook in webhooks:
    client.webhooks.register(**webhook)

# Your message queue subscribes to events
# and builds projections, triggers actions, etc.
```

**Integration Time:** 1-2 weeks
**Complexity:** High

---

#### Level 4: Multi-Tenant SaaS Integration

**What it does:** Complete white-label RAG as service layer

```python
# Each tenant gets isolated namespace
class TenantRAGClient:
    def __init__(self, tenant_id: str, api_key: str):
        self.client = Client(api_key=api_key)
        self.tenant_id = tenant_id

    def query(self, question: str, user_id: str):
        response = self.client.queries.create(
            question=question,
            user_id=f"{self.tenant_id}:{user_id}",
            metadata={"tenant_id": self.tenant_id}
        )
        return response

    def register_webhook(self, url: str, events: List[str]):
        self.client.webhooks.register(
            url=url,
            events=events,
            headers={"X-Tenant-ID": self.tenant_id}
        )

# Usage
for tenant in get_all_tenants():
    client = TenantRAGClient(tenant.id, tenant.api_key)
    client.register_webhook(
        url=f"{tenant.webhook_url}/rag",
        events=["query.completed", "document.ingested"]
    )
```

**Integration Time:** 2-4 weeks
**Complexity:** Very High

---

## Scalability & Performance

### Webhook Scaling Architecture

```
┌──────────────────────────────────────────────────┐
│            WEBHOOK DELIVERY SYSTEM               │
├──────────────────────────────────────────────────┤
│                                                  │
│  [Event Generated]                              │
│    ↓                                             │
│  PostgreSQL Event Log                           │
│  (durable, queryable)                           │
│    ↓                                             │
│  Redis Queue (webhook_deliveries)               │
│  - FIFO per tenant                              │
│  - TTL: 24 hours                                │
│  - DLQ for failed deliveries                    │
│    ↓                                             │
│  ┌─────────────────────────────────┐            │
│  │ Delivery Workers (Horizontal)   │            │
│  │ ├─ Worker 1 (CPU1)              │            │
│  │ ├─ Worker 2 (CPU2)              │            │
│  │ ├─ Worker 3 (CPU3)              │            │
│  │ └─ Auto-scale 1-50 based on Q   │            │
│  └─────────────────────────────────┘            │
│    ↓                                             │
│  Webhook URLs (your infrastructure)             │
│    ↓                                             │
│  Callback Status → PostgreSQL                   │
│  (success/retry/failed)                         │
│                                                  │
└──────────────────────────────────────────────────┘
```

### Performance Targets

| Metric | Target |
|--------|--------|
| Event generation latency | <10ms |
| Webhook queue time | <100ms |
| First delivery attempt | <5 seconds |
| Median delivery latency | <1 second |
| 99th percentile latency | <10 seconds |
| Success rate (w/ retries) | >99.5% |
| Throughput (webhooks/sec) | 10,000+ |

### Scaling Parameters

```yaml
# config/webhook_config.yaml
webhook_delivery:
  # Worker pool
  min_workers: 3
  max_workers: 50
  scale_up_threshold: 80%  # CPU utilization

  # Retry policy
  max_retries: 4
  initial_backoff_ms: 1000
  max_backoff_ms: 300000  # 5 minutes
  backoff_multiplier: 2.0

  # Timeout
  request_timeout_seconds: 10

  # Batch delivery
  batch_size: 100
  batch_timeout_ms: 500

  # Deduplication
  dedup_window_hours: 1
  allow_duplicates_if_urgent: true
```

---

## Observability & Monitoring

### Webhook Monitoring Dashboard

```
┌────────────────────────────────────────────┐
│         WEBHOOK METRICS DASHBOARD          │
├────────────────────────────────────────────┤
│                                            │
│ Real-time Metrics:                        │
│ ├─ Events generated: 15,234               │
│ ├─ Webhooks registered: 42                │
│ ├─ Deliveries pending: 127                │
│ ├─ Success rate (24h): 99.87%             │
│ └─ Avg delivery time: 245ms               │
│                                            │
│ By Event Type:                            │
│ ├─ query.completed: 8,420 (3.2 ops/min)  │
│ ├─ document.ingested: 1,250 (0.4 ops/min)│
│ ├─ query.escalated: 320 (0.12 ops/min)   │
│ └─ job.progress: 5,244 (2.0 ops/min)     │
│                                            │
│ Failed Deliveries (last 24h):            │
│ ├─ Timeout errors: 8                     │
│ ├─ Network errors: 3                     │
│ ├─ Webhook URL 404: 2                    │
│ └─ Auth failures: 1                      │
│                                            │
│ Action Required:                          │
│ ⚠️  webhook_whk_001 failing (4 retries)  │
│     → Action: Retry / Remove / Debug     │
│                                            │
└────────────────────────────────────────────┘
```

### Logging for Webhooks

```
[2026-01-07T10:16:00.125Z] webhook.delivery
  webhook_id=whk_001
  event_id=evt_abc123
  event_type=query.completed
  delivery_attempt=1
  target_url=https://myapp.example.com/webhooks
  status=sent
  http_status=200
  response_time_ms=245
  retry_after=null
  message="Delivery successful"

[2026-01-07T10:16:01.542Z] webhook.delivery
  webhook_id=whk_002
  event_id=evt_abc123
  event_type=query.completed
  delivery_attempt=1
  target_url=https://crm.example.com/webhooks
  status=failed
  error_code=TIMEOUT
  http_status=null
  retry_after=5000
  message="Connection timeout (10s)"
  next_retry_at=2026-01-07T10:16:05.542Z
```

### Tracing Webhook Delivery

```
TRACE webhook_delivery_evt_abc123
├─ event.generated
│  ├─ timestamp: 2026-01-07T10:16:00.000Z
│  ├─ type: query.completed
│  └─ payload_size: 2.4KB
│
├─ webhook.matched
│  ├─ webhooks_found: 3
│  ├─ whk_001: query.* (match)
│  ├─ whk_002: query.* (match)
│  └─ whk_003: document.* (no match)
│
├─ delivery_queue.enqueued
│  ├─ timestamp: 2026-01-07T10:16:00.005Z
│  ├─ queue_depth_before: 127
│  └─ priority: normal
│
├─ delivery.whk_001
│  ├─ attempt: 1
│  ├─ worker_id: worker_42
│  ├─ request_sent: 2026-01-07T10:16:00.120Z
│  ├─ http_method: POST
│  ├─ http_status: 200
│  ├─ response_time_ms: 245
│  └─ status: success
│
└─ delivery.whk_002
   ├─ attempt: 1
   ├─ worker_id: worker_38
   ├─ request_sent: 2026-01-07T10:16:00.118Z
   ├─ http_status: 502
   ├─ error: "Bad Gateway"
   ├─ retry_after: 5000
   └─ status: will_retry
```

---

## Security in Integrations

### Webhook Security Best Practices

#### 1. HMAC Signature Validation (Server-side)

```python
# RAG Service generates signature
import hmac
import hashlib
import base64

payload = json.dumps(event_data)
secret = webhook.secret_key  # Stored securely

signature = base64.b64encode(
    hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).digest()
).decode()

headers = {
    "X-Signature": f"sha256={signature}"
}
```

#### 2. HMAC Signature Validation (Client-side)

```python
# Your webhook handler validates signature
import hmac
import hashlib
import base64

@app.post("/webhooks/rag")
def handle_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-Signature")

    # Retrieve secret from your secure vault
    webhook_secret = get_secret("webhook_supportrag_secret")

    # Compute expected signature
    expected_sig = base64.b64encode(
        hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).digest()
    ).decode()
    expected_sig = f"sha256={expected_sig}"

    # Constant-time comparison (prevent timing attacks)
    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Process event
    event = json.loads(payload)
    handle_event(event)
    return {"status": "received"}
```

#### 3. Secret Rotation

```yaml
# Rotate secrets every 90 days
webhook_secret_rotation:
  interval_days: 90
  grace_period_days: 30  # Both old & new secrets accepted

  # When rotating:
  # 1. Generate new secret
  # 2. Mark old as deprecated
  # 3. For 30 days: accept both
  # 4. After 30 days: only accept new
  # 5. Delete old after 90 days
```

#### 4. Rate Limiting Webhooks

```
Your webhook endpoint should implement rate limiting:

Per-Tenant Limits:
├─ Free tier: 100 webhooks/hour
├─ Pro tier: 10,000 webhooks/hour
└─ Enterprise: Unlimited

Per-IP Limits:
├─ Max 1000 concurrent connections
├─ Max 100 retries/hour per endpoint
└─ Circuit breaker if >50% failures
```

#### 5. Webhook Endpoint Best Practices

```python
@app.post("/webhooks/supportrag")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    # 1. Verify signature immediately
    await verify_webhook_signature(request)

    # 2. Extract idempotency key
    event_id = request.headers.get("X-Event-ID")

    # 3. Check if already processed (dedup)
    if redis.exists(f"webhook_processed:{event_id}"):
        return {"status": "already_processed", "event_id": event_id}

    # 4. Mark as processed (with short TTL)
    redis.setex(f"webhook_processed:{event_id}", 3600, "1")

    # 5. Extract payload
    payload = await request.json()

    # 6. Validate payload structure
    validate_webhook_payload(payload)

    # 7. Queue for async processing (don't block)
    background_tasks.add_task(process_webhook_async, payload)

    # 8. Return immediately (200 OK)
    return {"status": "received", "event_id": event_id}

# Process webhook in background
async def process_webhook_async(payload: dict):
    try:
        event_type = payload["event_type"]

        if event_type == "query.completed":
            await handle_query_completed(payload)
        elif event_type == "document.ingested":
            await handle_document_ingested(payload)
        elif event_type == "query.escalated":
            await handle_query_escalated(payload)

        # Log success
        logger.info(f"Webhook processed: {event_type}")

    except Exception as e:
        # Alert on errors
        logger.error(f"Webhook processing failed: {e}")
        send_alert(f"Webhook error: {e}")
```

#### 6. Endpoint Security Checklist

```yaml
Security Checklist:
├─ ✅ HTTPS only (TLS 1.3+)
├─ ✅ HMAC signature validation
├─ ✅ Idempotency key tracking
├─ ✅ Input validation + sanitization
├─ ✅ Rate limiting per source
├─ ✅ Async processing (don't block)
├─ ✅ Error handling (don't leak info)
├─ ✅ Logging (but not secrets)
├─ ✅ Monitoring + alerting
├─ ✅ Retry logic (exponential backoff)
├─ ✅ Circuit breaker pattern
└─ ✅ Regular security audit
```

---

## Appendix: Integration Checklist

### Before Going Live

- [ ] API authentication working (API key or OAuth)
- [ ] Webhook registration tested
- [ ] HMAC signature validation implemented
- [ ] Deduplication logic in place
- [ ] Error handling comprehensive
- [ ] Rate limits understood
- [ ] Monitoring/alerting configured
- [ ] Load testing completed
- [ ] Disaster recovery tested
- [ ] Documentation complete
- [ ] Security review passed
- [ ] Staging environment tested
- [ ] Canary deployment validated
- [ ] Runbooks prepared
- [ ] Team trained

---

**Document Version:** INTEGRATION_ARCHITECTURE_v1.0
**Audience:** Staff Engineers, Architects, Integration Partners
**Status:** Approved for Implementation
