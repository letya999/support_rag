# API Endpoints Reference

Complete reference for all Support RAG API endpoints (v1).

**Base URL:** `http://localhost:8000/api/v1`  
**Response Format:** All endpoints return `Envelope` pattern with `data`, `error`, and `meta` fields.

## Table of Contents

1. [Chat & RAG Generation](#1-chat--rag-generation)
2. [Knowledge Base Ingestion](#2-knowledge-base-ingestion)
3. [Autoclassification](#3-autoclassification)
4. [Categories & Intents (Taxonomy)](#4-categories--intents-taxonomy)
5. [Channels Integration](#5-channels-integration)
6. [Message History](#6-message-history)
7. [Cache Management](#7-cache-management)
8. [Chunks Management](#8-chunks-management)
9. [Dataset Generation](#9-dataset-generation)
10. [Configuration](#10-configuration)
11. [System Health](#11-system-health)

---

## 1. Chat & RAG Generation

### POST `/api/v1/chat/completions`
**Purpose:** Synchronous RAG query with full answer returned at once.

**Request:**
```json
{
  "question": "How to reset my password?",
  "session_id": "uuid-optional",
  "user_id": "user123",
  "conversation_history": [
    {"role": "user", "content": "Previous message"},
    {"role": "assistant", "content": "Previous response"}
  ],
  "user_metadata": {
    "channel": "telegram",
    "language": "en"
  }
}
```

**Response:**
```json
{
  "data": {
    "question": "How to reset my password?",
    "answer": "Go to Settings → Security → Reset Password...",
    "sources": [
      {
        "document_id": "doc-123",
        "title": "Password Reset Guide",
        "excerpt": "Reset password steps...",
        "relevance": 0.95,
        "metadata": {
          "category": "Account Management",
          "intent": "password_reset"
        }
      }
    ],
    "confidence": 0.92,
    "query_id": "query-uuid",
    "pipeline_metadata": {
      "dialog_state": "ANSWERED",
      "search_method": "hybrid",
      "num_retrieved": 5
    }
  },
  "error": null,
  "meta": {
    "trace_id": "trace-uuid",
    "request_id": "req-uuid"
  }
}
```

---

### POST `/api/v1/chat/stream`
**Purpose:** Server-Sent Events (SSE) streaming generation.

**Request:** Same as `/completions`

**Response (SSE Stream):**
```
event: token
data: {"content": "Go "}

event: token
data: {"content": "to "}

event: sources
data: {"sources": [...]}

event: done
data: {"query_id": "...", "confidence": 0.92}
```

**Client example (JavaScript):**
```javascript
const eventSource = new EventSource('/api/v1/chat/stream');
eventSource.addEventListener('token', (e) => {
  const data = JSON.parse(e.data);
  console.log(data.content);
});
eventSource.addEventListener('done', (e) => {
  eventSource.close();
});
```

---

### POST `/api/v1/chat/escalate`
**Purpose:** Manually trigger escalation to human operator.

**Request:**
```json
{
  "session_id": "session-uuid",
  "reason": "User requested human assistance",
  "user_id": "user123"
}
```

**Response:**
```json
{
  "data": {
    "status": "escalated",
    "session_id": "session-uuid"
  },
  "meta": {"trace_id": "..."}
}
```

---

### POST `/api/v1/chat/sessions/{session_id}/escalate`
**Purpose:** Escalate a specific session by ID.

**Response:** Same as above.

---

## 2. Knowledge Base Ingestion

### GET `/api/v1/ingestion/contract`
**Purpose:** Get API contract (supported formats, limits).

**Response:**
```json
{
  "data": {
    "supported_formats": ["json", "csv", "pdf", "docx"],
    "max_pairs": 10000,
    "max_question_length": 500,
    "max_answer_length": 2000,
    "json_schema": [
      {"field": "question", "type": "string", "required": true},
      {"field": "answer", "type": "string", "required": true},
      {"field": "metadata", "type": "object", "required": false}
    ]
  }
}
```

---

### POST `/api/v1/ingestion/upload`
**Purpose:** Upload file → create staging draft in Redis.

**Request (multipart/form-data):**
```bash
curl -X POST http://localhost:8000/api/v1/ingestion/upload \
  -F "file=@qa_data.json"
```

**Response:**
```json
{
  "data": {
    "draft_id": "draft-uuid",
    "filename": "qa_data.json",
    "extracted_pairs": [
      {"question": "...", "answer": "...", "metadata": {...}},
      ...
    ],
    "total_pairs": 150
  }
}
```

---

### GET `/api/v1/ingestion/drafts`
**Purpose:** List all staging drafts with optional filtering.

**Query Params:**
- `draft_ids` (optional): Filter by specific draft IDs
- `search` (optional): Search by filename

**Response:**
```json
{
  "data": [
    {
      "draft_id": "draft-uuid",
      "filename": "qa_data.json",
      "status": "pending",
      "created_at": "2026-01-12T20:00:00Z",
      "chunks_count": 150
    }
  ]
}
```

---

### POST `/api/v1/ingestion/drafts`
**Purpose:** Create a manual draft (without file upload).

**Request:**
```json
{
  "filename": "manual_draft.json",
  "chunks": [
    {
      "question": "How to cancel order?",
      "answer": "Go to Orders → Select order → Cancel",
      "metadata": {
        "category": "Orders",
        "intent": "order_cancellation"
      }
    }
  ]
}
```

**Response:**
```json
{
  "data": {
    "draft_id": "draft-uuid",
    "total_chunks": 1
  }
}
```

---

### GET `/api/v1/ingestion/drafts/{draft_id}`
**Purpose:** Get a specific staging draft with all chunks.

**Response:**
```json
{
  "data": {
    "draft_id": "draft-uuid",
    "filename": "qa_data.json",
    "chunks": [
      {
        "chunk_id": "chunk-uuid",
        "question": "...",
        "answer": "...",
        "metadata": {...}
      }
    ],
    "total_chunks": 150
  }
}
```

---

### DELETE `/api/v1/ingestion/drafts/{draft_id}`
**Purpose:** Delete a staging draft.

**Response:**
```json
{
  "data": {"status": "deleted", "draft_id": "draft-uuid"}
}
```

---

### POST `/api/v1/ingestion/drafts/{draft_id}/chunks`
**Purpose:** Add chunks to existing draft.

**Request:**
```json
{
  "chunks": [
    {"question": "...", "answer": "...", "metadata": {...}}
  ]
}
```

---

### DELETE `/api/v1/ingestion/drafts/{draft_id}/chunks/{chunk_id}`
**Purpose:** Delete a specific chunk from draft.

---

### PATCH `/api/v1/ingestion/drafts/{draft_id}/chunks`
**Purpose:** Update multiple chunks in draft (batch edit).

**Request:**
```json
{
  "updates": [
    {
      "chunk_id": "chunk-uuid",
      "question": "Updated question",
      "answer": "Updated answer",
      "metadata": {"category": "New Category"}
    }
  ]
}
```

---

### POST `/api/v1/ingestion/commit`
**Purpose:** Commit staging draft to production (Postgres + Qdrant).

**Request:**
```json
{
  "draft_id": "draft-uuid",
  "action": "commit"
}
```

**Response:**
```json
{
  "data": {
    "status": "committed",
    "draft_id": "draft-uuid",
    "indexed_count": 150,
    "failed_count": 0
  }
}
```

---

### DELETE `/api/v1/ingestion/drafts/all`
**Purpose:** Delete ALL staging drafts (use with caution).

---

## 3. Autoclassification

### POST `/api/v1/autoclassify/{draft_id}/discovery`
**Purpose:** LLM-based discovery classification (auto-generate categories/intents).

**Query Params:**
- `update_staging` (default: false): Auto-update draft with results

**Response:**
```json
{
  "data": {
    "categories": [
      {
        "name": "Account Management",
        "intents": [
          {
            "name": "password_reset",
            "chunks": [
              {
                "chunk_id": "chunk-uuid",
                "question": "...",
                "answer": "...",
                "confidence": 0.92
              }
            ]
          }
        ]
      }
    ]
  }
}
```

---

### PATCH `/api/v1/autoclassify/{draft_id}/chunks`
**Purpose:** Manually update chunk metadata after classification review.

**Request:**
```json
{
  "updates": [
    {
      "chunk_id": "chunk-uuid",
      "metadata": {
        "category": "Corrected Category",
        "intent": "corrected_intent"
      }
    }
  ]
}
```

---

### POST `/api/v1/autoclassify/{draft_id}/zeroshot`
**Purpose:** Zero-shot classification against system taxonomy (no LLM).

**Request:**
```json
{
  "update_staging": true
}
```

**Response:** Same grouped structure as discovery.

---

### POST `/api/v1/autoclassify/batch/custom`
**Purpose:** Batch zero-shot classification with custom taxonomy.

**Request:**
```json
{
  "taxonomy": [
    {
      "name": "Billing",
      "intents": ["refund_request", "payment_issue", "invoice_query"]
    },
    {
      "name": "Technical Support",
      "intents": ["bug_report", "feature_request"]
    }
  ],
  "draft_ids": ["draft-1", "draft-2"],
  "update_staging": false
}
```

**Response:**
```json
{
  "data": {
    "draft-1": {
      "categories": [...]
    },
    "draft-2": {
      "categories": [...]
    }
  }
}
```

---

## 4. Categories & Intents (Taxonomy)

### GET `/api/v1/categories/tree`
**Purpose:** Get full category/intent taxonomy tree.

**Response:**
```json
{
  "data": {
    "categories": [
      {
        "name": "Account Management",
        "intents": ["password_reset", "account_deletion", "profile_update"],
        "description": "User account related queries"
      }
    ]
  }
}
```

---

### PATCH `/api/v1/categories/rename`
**Purpose:** Rename category or intent (updates all documents).

**Request:**
```json
{
  "old_name": "Account Mgmt",
  "new_name": "Account Management",
  "type": "category"
}
```

---

### POST `/api/v1/categories/sync`
**Purpose:** Sync registry from DB (regenerate `intents_registry.yaml`).

**Response:**
```json
{
  "data": {
    "status": "synced",
    "categories_count": 15,
    "intents_count": 87
  }
}
```

---

## 5. Channels Integration

### POST `/api/v1/channels/messages`
**Purpose:** Send message to a channel (bypassing RAG).

**Request:**
```json
{
  "channel": "telegram",
  "user_id": "telegram-user-id",
  "message": "Hello from Support RAG!"
}
```

**Response:**
```json
{
  "data": {
    "message_id": "msg-123",
    "status": "sent"
  }
}
```

---

### PATCH `/api/v1/channels/messages/{message_id}`
**Purpose:** Edit a message in a channel.

**Request:**
```json
{
  "message": "Updated message content",
  "user_id": "telegram-user-id"
}
```

---

### DELETE `/api/v1/channels/messages/{message_id}`
**Purpose:** Delete a message.

**Query Params:**
- `user_id`: Required for Telegram

---

## 6. Message History

### GET `/api/v1/history`
**Purpose:** Get message history from database.

**Query Params:**
- `user_id` (required): User ID
- `role` (optional): Filter by role (user/assistant/system)
- `limit` (default: 20): Max messages to return

**Response:**
```json
{
  "data": [
    {
      "message_id": "msg-123",
      "role": "user",
      "content": "How to reset password?",
      "timestamp": "2026-01-12T20:00:00Z"
    }
  ]
}
```

---

### DELETE `/api/v1/history`
**Purpose:** Delete history for a user.

**Request:**
```json
{
  "user_id": "user123",
  "method": "soft"
}
```

---

## 7. Cache Management

### GET `/api/v1/cache/session_state`
**Purpose:** Get active session state from Redis.

**Query Params:**
- `user_id` (required)
- `limit` (default: 10)

**Response:**
```json
{
  "data": [
    {
      "role": "system",
      "content": "Session State: ANSWERED",
      "timestamp": "2026-01-12T20:00:00Z",
      "metadata": {
        "dialog_state": "ANSWERED",
        "last_activity_time": "2026-01-12T20:00:00Z"
      }
    }
  ],
  "meta": {
    "extra": {
      "active_session_id": "session-uuid"
    }
  }
}
```

---

### GET `/api/v1/cache/recent_messages`
**Purpose:** Get recent messages from Redis session (not DB).

**Query Params:** Same as session_state

---

### DELETE `/api/v1/cache`
**Purpose:** Clear cache for user or all.

**Query Params:**
- `user_id` (optional): Specific user or "all"

---

### GET `/api/v1/cache/status`
**Purpose:** Get Redis status and metrics.

**Response:**
```json
{
  "data": {
    "memory_usage_mb": 45.2,
    "total_keys": 1250,
    "hit_rate": 0.85,
    "connected": true
  }
}
```

---

## 8. Chunks Management

### GET `/api/v1/chunks`
**Purpose:** Search and filter chunks in production database.

**Query Params:**
- `page` (default: 1)
- `size` (default: 50, max: 100)
- `search` (optional): Full-text search
- `chunk_id` (optional): Filter by specific ID
- `intent` (optional)
- `category` (optional)
- `source_document` (optional)
- `requires_handoff` (optional)
- `extraction_date` (optional)

**Response:**
```json
{
  "data": [
    {
      "id": 123,
      "content": "Q: How to reset password?\nA: Go to Settings...",
      "metadata": {
        "category": "Account Management",
        "intent": "password_reset",
        "source": "manual_upload"
      }
    }
  ],
  "meta": {
    "pagination": {
      "limit": 50,
      "offset": 0,
      "total": 1500
    }
  }
}
```

---

### GET `/api/v1/chunks/{chunk_id}`
**Purpose:** Get specific chunk by ID.

---

### PATCH `/api/v1/chunks/{chunk_id}`
**Purpose:** Update chunk content or metadata.

**Request:**
```json
{
  "content": "Updated Q&A content",
  "metadata": {
    "category": "New Category"
  }
}
```

---

### DELETE `/api/v1/chunks/{chunk_id}`
**Purpose:** Delete chunk from database and vector store.

---

## 9. Dataset Generation

### POST `/api/v1/dataset/generate/simple`
**Purpose:** Generate simple Q&A pairs (synthetic).

**Request:**
```json
{
  "description": "E-commerce returns and refunds",
  "count": 50,
  "is_random": false
}
```

**Response:**
```json
{
  "data": {
    "items": [
      {"question": "...", "answer": "..."}
    ],
    "count": 50
  }
}
```

---

### POST `/api/v1/dataset/generate/ground-truth`
**Purpose:** Generate ground truth eval dataset from existing Q&A.

**Request:**
```json
{
  "input_data": [
    {"question": "...", "answer": "..."}
  ],
  "adversarial_level": 0.5
}
```

**Response:**
```json
{
  "data": {
    "items": [
      {
        "input": "Paraphrased question",
        "expected_output": "Expected answer",
        "contexts": ["Original Q&A"],
        "metadata": {...}
      }
    ],
    "count": 50
  }
}
```

---

### POST `/api/v1/dataset/generate/ground-truth/from-file`
**Purpose:** Generate ground truth from uploaded file.

**Request (multipart):**
```bash
curl -X POST http://localhost:8000/api/v1/dataset/generate/ground-truth/from-file \
  -F "file=@qa_data.json" \
  -F "adversarial_level=0.7"
```

---

### POST `/api/v1/dataset/save`
**Purpose:** Save dataset to disk.

**Request:**
```json
{
  "name": "eval_dataset_v1",
  "items": [...],
  "as_ground_truth": true
}
```

---

### POST `/api/v1/dataset/sync-langfuse`
**Purpose:** Sync dataset to Langfuse for evaluation.

---

### GET `/api/v1/dataset/list`
**Purpose:** List all saved datasets.

**Response:**
```json
{
  "data": {
    "datasets": ["eval_dataset_v1.json", "ground_truth_v2.json"]
  }
}
```

---

## 10. Configuration

### GET `/api/v1/config/full`
**Purpose:** Get full system config (secrets masked).

**Response:**
```json
{
  "data": {
    "APP_NAME": "Support RAG",
    "OPENAI_API_KEY": "***",
    "DATABASE_URL": "postgresql://...",
    "REDIS_URL": "redis://localhost:6379"
  }
}
```

---

### GET `/api/v1/config/phrases`
**Purpose:** Get system phrases (greetings, fallbacks).

**Response:**
```json
{
  "data": {
    "welcome": "Привет! Я Support RAG бот.",
    "fallback": "К сожалению, я не нашел ответа в документах.",
    "escalate": "Перевожу на оператора."
  }
}
```

---

### POST `/api/v1/config/refresh`
**Purpose:** Regenerate pipeline_config.yaml from node configs.

**Response:**
```json
{
  "data": {
    "status": "refreshed",
    "nodes_count": 22
  }
}
```

---

## 11. System Health

### GET `/api/v1/health`
**Purpose:** System health check.

**Response:**
```json
{
  "data": {
    "status": "healthy",
    "database": "configured",
    "redis": "configured",
    "llm": "configured"
  }
}
```

---

### GET `/api/v1/ping`
**Purpose:** Simple ping/pong for uptime checks.

**Response:**
```json
{
  "data": "pong"
}
```

---

## Error Responses

All errors follow the same envelope pattern:

```json
{
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request format",
    "details": {
      "field": "question",
      "issue": "Field is required"
    }
  },
  "meta": {
    "trace_id": "trace-uuid",
    "request_id": "req-uuid"
  }
}
```

**Common HTTP Status Codes:**
- `200 OK` - Success
- `400 Bad Request` - Validation error
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

---

## Rate Limiting

Default limits (configurable):
- **Chat endpoints:** 60 requests/minute per user
- **Upload endpoints:** 10 requests/minute per user
- **All others:** 100 requests/minute per user

Headers returned:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1673552400
```

---

## Authentication

Currently **no authentication** required for local development.

For production, implement one of:
- API Key auth (header: `X-API-Key`)
- JWT tokens (header: `Authorization: Bearer <token>`)
- OAuth2 integration

---

## Interactive Documentation

**Swagger UI:** http://localhost:8000/docs  
**ReDoc:** http://localhost:8000/redoc  
**OpenAPI JSON:** http://localhost:8000/openapi.json

---

**Last Updated:** 2026-01-12  
**API Version:** v1
