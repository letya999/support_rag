# Support RAG Service - REST API & Webhooks Design

**Version:** 1.0
**Status:** Design Specification
**Author:** RAG Architecture Team (Staff Engineer Level)
**Last Updated:** 2026-01-07

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [API Design Principles](#api-design-principles)
3. [Core REST API](#core-rest-api)
4. [Document Management API](#document-management-api)
5. [Configuration & Admin API](#configuration--admin-api)
6. [Session & Context API](#session--context-api)
7. [Analytics & Monitoring API](#analytics--monitoring-api)
8. [Webhook Specifications](#webhook-specifications)
9. [Error Handling](#error-handling)
10. [Rate Limiting & Quotas](#rate-limiting--quotas)
11. [Security & Authentication](#security--authentication)
12. [Backwards Compatibility](#backwards-compatibility)

---

## Executive Summary

The Support RAG Service exposes **enterprise-grade APIs** designed for easy third-party integration. The API follows **REST + webhooks** patterns with:

- **3 API tiers**: Core RAG, Document Management, Admin
- **9 webhook event types**: Both incoming triggers and outgoing notifications
- **Stateless design**: Easy horizontal scaling
- **Strict versioning**: Breaking changes → major version bump
- **HATEOAS support**: Clients can discover endpoints dynamically
- **Async operations**: Long-running tasks return job IDs + webhooks for completion

**Key Design Goals:**
1. ✅ Easy integration for third-party developers
2. ✅ Production-ready with comprehensive monitoring
3. ✅ Multi-tenant capable (user_id + tenant_id separation)
4. ✅ Backwards compatible (old API versions remain supported)
5. ✅ Scalable (stateless, event-driven architecture)

---

## API Design Principles

### 1. RESTful Conventions
- **Resources** as nouns: `/documents`, `/sessions`, `/queries`
- **Actions** as verbs (HTTP methods): GET, POST, PUT, PATCH, DELETE
- **Hierarchical URIs**: `/documents/{doc_id}/versions/{version_id}`
- **Query parameters** for filtering/pagination: `?limit=20&offset=40&sort=created_at`

### 2. Versioning Strategy
- **Header-based versioning** (recommended for single-source-of-truth):
  ```
  Accept: application/vnd.supportrag.v1+json
  ```
- **URL-path versioning** (fallback for legacy clients):
  ```
  GET /api/v1/queries
  ```
- **Deprecation policy**: Min 6 months before removing old versions

### 3. Response Format
All responses follow a **standard envelope**:

```json
{
  "status": "success|error|pending",
  "data": { ... },
  "meta": {
    "request_id": "req_abc123xyz",
    "timestamp": "2026-01-07T10:15:30Z",
    "version": "1.0"
  },
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "message": "Query too long (max 2000 chars)",
      "field": "question",
      "details": { ... }
    }
  ]
}
```

### 4. Pagination
All list endpoints support:
- `limit`: Items per page (default: 20, max: 100)
- `offset`: Skip N items (for cursor-based: `cursor` param)
- `sort`: Sort field (default: `-created_at` for reverse chrono)

Response includes:
```json
{
  "data": [...],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 150,
    "has_next": true,
    "next_cursor": "crs_xyz789"
  }
}
```

### 5. Async Operations
Long-running operations (doc ingestion, evaluation) return immediately with a **job ID**:

```json
{
  "status": "pending",
  "data": {
    "job_id": "job_abc123",
    "status": "processing",
    "progress": 0.35,
    "eta_seconds": 45
  },
  "links": {
    "poll": "/api/v1/jobs/job_abc123",
    "cancel": "/api/v1/jobs/job_abc123/cancel"
  }
}
```

Client can:
- **Poll**: `GET /api/v1/jobs/{job_id}`
- **Webhook**: System sends `job.completed` event to registered webhook
- **WebSocket** (optional): Real-time updates

---

## Core REST API

### 1. Health & Status

#### `GET /health`
Check service health (dependencies included).

**Response:**
```json
{
  "status": "healthy",
  "data": {
    "service": "support-rag-v1.0.0",
    "uptime_seconds": 86400,
    "dependencies": {
      "postgres": "healthy",
      "qdrant": "healthy",
      "redis": "healthy",
      "openai": "healthy",
      "langfuse": "healthy"
    }
  },
  "meta": {
    "request_id": "req_health_001",
    "timestamp": "2026-01-07T10:15:30Z"
  }
}
```

**Status Codes:**
- `200 OK` - All healthy
- `503 Service Unavailable` - One or more deps down

---

### 2. Query & RAG Endpoints

#### `POST /api/v1/queries`
**Purpose:** Execute a single RAG query with optional context.

**Request:**
```json
{
  "question": "What's your return policy?",
  "conversation_history": [
    {
      "role": "user",
      "content": "I want to return an item",
      "timestamp": "2026-01-07T10:00:00Z"
    },
    {
      "role": "assistant",
      "content": "Sure, let me help you with that."
    }
  ],
  "user_id": "user_123",
  "session_id": "sess_xyz789",
  "metadata": {
    "source": "telegram",
    "language": "en",
    "device_id": "device_abc"
  },
  "options": {
    "use_hybrid_search": true,
    "use_reranking": true,
    "temperature": 0.1,
    "max_tokens": 500,
    "timeout_seconds": 30
  }
}
```

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "query_id": "q_abc123xyz",
    "answer": "Our return policy allows returns within 30 days...",
    "confidence": 0.92,
    "sources": [
      {
        "document_id": "doc_001",
        "title": "Return Policy FAQ",
        "excerpt": "...within 30 days of purchase...",
        "relevance_score": 0.95,
        "category": "returns",
        "url": "https://docs.example.com/returns"
      }
    ],
    "metadata": {
      "retrieval_mode": "hybrid",
      "documents_checked": 127,
      "documents_used": 2,
      "processing_time_ms": 245,
      "language_detected": "en"
    },
    "action": "auto_reply",
    "escalation_triggered": false,
    "cache_hit": false
  },
  "meta": {
    "request_id": "req_q_abc123xyz",
    "timestamp": "2026-01-07T10:15:30Z",
    "version": "1.0"
  }
}
```

**Response (Escalation):**
```json
{
  "status": "success",
  "data": {
    "query_id": "q_def456",
    "answer": null,
    "confidence": 0.15,
    "sources": [],
    "action": "escalate",
    "escalation_triggered": true,
    "escalation_reason": "Requires human review",
    "escalation_category": "billing_dispute",
    "suggested_team": "billing_support"
  }
}
```

**Status Codes:**
- `200 OK` - Query processed (auto_reply OR escalated)
- `400 Bad Request` - Invalid question (too short/long, invalid chars)
- `429 Too Many Requests` - Rate limit exceeded
- `503 Service Unavailable` - Database connection lost

**Query Limits:**
- Min length: 3 characters
- Max length: 2000 characters
- Conversation history: Max 20 turns
- Timeout: 30 seconds (configurable)

---

#### `GET /api/v1/queries/{query_id}`
Retrieve details of a past query (for audit/replay).

**Response:**
```json
{
  "status": "success",
  "data": {
    "query_id": "q_abc123xyz",
    "question": "What's your return policy?",
    "answer": "Our return policy...",
    "user_id": "user_123",
    "session_id": "sess_xyz789",
    "created_at": "2026-01-07T10:15:30Z",
    "processing_time_ms": 245,
    "feedback": {
      "rating": 5,
      "helpful": true,
      "comment": "Very helpful!"
    }
  }
}
```

---

#### `POST /api/v1/queries/{query_id}/feedback`
Submit feedback on a query result.

**Request:**
```json
{
  "rating": 5,
  "helpful": true,
  "correct": true,
  "comment": "Perfect answer!",
  "tags": ["fast", "relevant"]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "feedback_id": "fb_xyz",
    "query_id": "q_abc123xyz",
    "recorded_at": "2026-01-07T10:16:00Z"
  }
}
```

---

#### `GET /api/v1/search`
Raw document search (without RAG generation). Useful for **non-generative** search UIs.

**Query Parameters:**
```
GET /api/v1/search?q=return+policy&limit=10&filter=category:returns&sort=-relevance_score
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "query": "return policy",
    "results": [
      {
        "document_id": "doc_001",
        "title": "Return Policy FAQ",
        "category": "returns",
        "intent": "policy_info",
        "relevance_score": 0.95,
        "rank": 1,
        "excerpt": "...within 30 days of purchase...",
        "url": "https://docs.example.com/returns",
        "last_updated": "2025-12-01T00:00:00Z"
      }
    ],
    "total_results": 42,
    "search_time_ms": 85
  }
}
```

**Filters Supported:**
- `category:returns` - By category
- `intent:policy_info` - By intent
- `language:en` - By language
- `updated_after:2025-12-01` - By date
- `requires_handoff:true` - Escalation-prone docs

---

#### `GET /api/v1/search/advanced`
Advanced search with semantic expansion, synonym matching, etc.

**Query Parameters:**
```
GET /api/v1/search/advanced?q=shipping+time&expand_synonyms=true&use_multihop=true&max_hops=3
```

**Response:**
Similar to `/search`, but includes:
```json
{
  "data": {
    "results": [...],
    "query_expansion": {
      "original": "shipping time",
      "expanded_terms": ["delivery time", "shipping duration", "order arrival"],
      "applied_expansions": 2
    },
    "multihop_chains": [
      {
        "hop": 1,
        "subquery": "What is standard shipping?",
        "results": [...]
      }
    ]
  }
}
```

---

### 3. Batch Query Processing

#### `POST /api/v1/queries/batch`
Submit multiple queries at once (async).

**Request:**
```json
{
  "queries": [
    {
      "id": "q_batch_1",
      "question": "Return policy?",
      "user_id": "user_123"
    },
    {
      "id": "q_batch_2",
      "question": "Shipping cost?",
      "user_id": "user_123"
    }
  ],
  "callback_url": "https://myapp.example.com/webhooks/batch-complete",
  "notify_on": ["completed", "error"]
}
```

**Response:**
```json
{
  "status": "pending",
  "data": {
    "job_id": "job_batch_001",
    "total_queries": 2,
    "status": "processing",
    "progress": {
      "processed": 0,
      "succeeded": 0,
      "failed": 0
    }
  },
  "links": {
    "poll": "/api/v1/jobs/job_batch_001",
    "cancel": "/api/v1/jobs/job_batch_001/cancel",
    "results": "/api/v1/jobs/job_batch_001/results"
  }
}
```

Client will receive webhook when done (or poll for results).

---

## Document Management API

### 1. Upload & Processing

#### `POST /api/v1/documents/upload`
Upload raw documents (PDF, DOCX, JSON, CSV) for processing.

**Request:**
```
Content-Type: multipart/form-data

{
  "files": [file1.pdf, file2.docx],
  "metadata": {
    "category": "faq",
    "language": "en",
    "source": "customer_service",
    "tags": ["product", "returns"]
  },
  "auto_classify": true,
  "validate_format": true
}
```

**Response:**
```json
{
  "status": "pending",
  "data": {
    "job_id": "job_upload_001",
    "files_received": 2,
    "status": "validating",
    "files": [
      {
        "filename": "file1.pdf",
        "size_bytes": 450000,
        "status": "processing",
        "estimated_qa_pairs": 42
      }
    ]
  },
  "links": {
    "poll": "/api/v1/jobs/job_upload_001",
    "webhook_url": "subscribe to job.completed event"
  }
}
```

---

#### `GET /api/v1/jobs/{job_id}`
Poll job status (upload, ingestion, evaluation, etc.).

**Response:**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_upload_001",
    "type": "document_upload",
    "status": "completed",
    "created_at": "2026-01-07T10:00:00Z",
    "completed_at": "2026-01-07T10:15:00Z",
    "result": {
      "total_files": 2,
      "files_processed": 2,
      "qa_pairs_extracted": 84,
      "qa_pairs_validated": 82,
      "qa_pairs_ingested": 82,
      "warnings": [
        {
          "file": "file2.docx",
          "message": "2 duplicate Q&A pairs found and skipped"
        }
      ],
      "next_step": "review_metadata",
      "review_url": "/api/v1/documents/review?job_id=job_upload_001"
    }
  }
}
```

**Possible Statuses:**
- `pending` - Waiting to start
- `processing` - In progress
- `waiting_input` - Requires user action (e.g., metadata review)
- `completed` - Success
- `failed` - Error occurred
- `cancelled` - User cancelled

---

#### `POST /api/v1/jobs/{job_id}/cancel`
Cancel a pending/processing job.

**Response:**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_upload_001",
    "status": "cancelled",
    "reason": "User cancelled",
    "cancelled_at": "2026-01-07T10:20:00Z"
  }
}
```

---

### 2. Metadata Review & Classification

#### `GET /api/v1/documents/pending-review`
Get Q&A pairs awaiting metadata review.

**Query Parameters:**
```
GET /api/v1/documents/pending-review?job_id=job_upload_001&limit=20
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_upload_001",
    "qa_pairs": [
      {
        "qa_id": "qa_001",
        "question": "What is your return policy?",
        "answer": "We accept returns within 30 days...",
        "metadata": {
          "category": "returns",
          "intent": "policy_info",
          "requires_handoff": false,
          "confidence": {
            "category": 0.92,
            "intent": 0.88
          }
        },
        "auto_generated": true,
        "needs_review": true
      }
    ],
    "total_pending": 2,
    "job_status": "waiting_input"
  }
}
```

---

#### `POST /api/v1/documents/qa-pairs/batch-update`
Correct or approve metadata for multiple Q&A pairs.

**Request:**
```json
{
  "updates": [
    {
      "qa_id": "qa_001",
      "metadata": {
        "category": "returns",
        "intent": "policy_info",
        "requires_handoff": false
      },
      "approved": true
    },
    {
      "qa_id": "qa_002",
      "metadata": {
        "category": "shipping",
        "intent": "cost_inquiry",
        "requires_handoff": false
      },
      "approved": true
    }
  ],
  "action": "approve_and_ingest"
}
```

**Response:**
```json
{
  "status": "pending",
  "data": {
    "job_id": "job_ingest_001",
    "total_updated": 2,
    "total_ingested": 2,
    "status": "indexing",
    "progress": 0.50
  }
}
```

---

#### `POST /api/v1/documents/qa-pairs/{qa_id}/split`
Split a Q&A pair into multiple (if it covers multiple topics).

**Request:**
```json
{
  "question": "What is your return and shipping policy?",
  "splits": [
    {
      "question": "What is your return policy?",
      "answer": "We accept returns within 30 days..."
    },
    {
      "question": "What is your shipping cost?",
      "answer": "Shipping is $5.99 for standard delivery..."
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "original_qa_id": "qa_001",
    "splits": [
      { "qa_id": "qa_001", "question": "..." },
      { "qa_id": "qa_001_split_1", "question": "..." }
    ]
  }
}
```

---

### 3. Document Management

#### `GET /api/v1/documents`
List all ingested documents (paginated).

**Query Parameters:**
```
GET /api/v1/documents?limit=20&offset=0&category=returns&sort=-created_at
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "documents": [
      {
        "document_id": "doc_001",
        "title": "Return Policy FAQ",
        "category": "returns",
        "qa_pairs_count": 12,
        "created_at": "2025-12-15T00:00:00Z",
        "updated_at": "2026-01-05T00:00:00Z",
        "status": "active",
        "language": "en",
        "metadata": {
          "source": "customer_service",
          "tags": ["policy", "faq"]
        },
        "links": {
          "self": "/api/v1/documents/doc_001",
          "qa_pairs": "/api/v1/documents/doc_001/qa-pairs"
        }
      }
    ],
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 156,
      "has_next": true
    }
  }
}
```

---

#### `GET /api/v1/documents/{document_id}`
Get document details with all Q&A pairs.

**Response:**
```json
{
  "status": "success",
  "data": {
    "document_id": "doc_001",
    "title": "Return Policy FAQ",
    "category": "returns",
    "qa_pairs": [
      {
        "qa_id": "qa_001",
        "question": "What is your return policy?",
        "answer": "We accept returns within 30 days...",
        "metadata": {
          "intent": "policy_info",
          "requires_handoff": false
        }
      }
    ],
    "created_at": "2025-12-15T00:00:00Z",
    "updated_at": "2026-01-05T00:00:00Z",
    "language": "en"
  }
}
```

---

#### `PUT /api/v1/documents/{document_id}`
Update document metadata (category, tags, status).

**Request:**
```json
{
  "category": "returns",
  "tags": ["policy", "faq", "updated"],
  "status": "active"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "document_id": "doc_001",
    "updated_at": "2026-01-07T10:16:00Z",
    "changes": {
      "tags": ["policy", "faq", "updated"]
    }
  }
}
```

---

#### `DELETE /api/v1/documents/{document_id}`
Archive/soft-delete a document (not physically deleted, marked as inactive).

**Query Parameters:**
```
DELETE /api/v1/documents/doc_001?cascade=true  (also delete Q&A pairs)
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "document_id": "doc_001",
    "status": "archived",
    "archived_at": "2026-01-07T10:16:30Z",
    "qa_pairs_archived": 12
  }
}
```

---

#### `GET /api/v1/documents/{document_id}/versions`
Get version history (if versioning is enabled).

**Response:**
```json
{
  "status": "success",
  "data": {
    "document_id": "doc_001",
    "versions": [
      {
        "version_id": "v_2",
        "created_at": "2026-01-05T10:00:00Z",
        "qa_pairs_count": 12,
        "changes": "Updated 2 Q&A pairs"
      },
      {
        "version_id": "v_1",
        "created_at": "2025-12-15T00:00:00Z",
        "qa_pairs_count": 10,
        "changes": "Initial upload"
      }
    ]
  }
}
```

---

### 4. Q&A Pair Management

#### `GET /api/v1/qa-pairs/{qa_id}`
Get a single Q&A pair.

**Response:**
```json
{
  "status": "success",
  "data": {
    "qa_id": "qa_001",
    "question": "What is your return policy?",
    "answer": "We accept returns within 30 days of purchase...",
    "document_id": "doc_001",
    "metadata": {
      "category": "returns",
      "intent": "policy_info",
      "requires_handoff": false,
      "confidence": {
        "category": 0.92,
        "intent": 0.88
      }
    },
    "statistics": {
      "times_retrieved": 127,
      "avg_user_rating": 4.7,
      "helpful_count": 95,
      "unhelpful_count": 5
    },
    "created_at": "2025-12-15T00:00:00Z",
    "updated_at": "2026-01-05T00:00:00Z"
  }
}
```

---

#### `PUT /api/v1/qa-pairs/{qa_id}`
Update a Q&A pair's content or metadata.

**Request:**
```json
{
  "question": "What is your return policy?",
  "answer": "We accept returns within 30 days of purchase, excluding final sale items...",
  "metadata": {
    "category": "returns",
    "intent": "policy_info",
    "requires_handoff": false
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "qa_id": "qa_001",
    "updated_at": "2026-01-07T10:17:00Z",
    "reindexed": true
  }
}
```

---

#### `DELETE /api/v1/qa-pairs/{qa_id}`
Archive a Q&A pair.

**Response:**
```json
{
  "status": "success",
  "data": {
    "qa_id": "qa_001",
    "status": "archived",
    "archived_at": "2026-01-07T10:17:30Z"
  }
}
```

---

#### `GET /api/v1/qa-pairs/search`
Full-text search across Q&A pairs.

**Query Parameters:**
```
GET /api/v1/qa-pairs/search?q=return&fields=question,answer&limit=50
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "query": "return",
    "results": [
      {
        "qa_id": "qa_001",
        "question": "What is your return policy?",
        "answer": "...",
        "matched_fields": ["question"],
        "relevance": 0.98
      }
    ],
    "total": 15,
    "search_time_ms": 45
  }
}
```

---

## Configuration & Admin API

### 1. System Configuration

#### `GET /api/v1/config`
Get current system configuration (read-only for non-admins).

**Response:**
```json
{
  "status": "success",
  "data": {
    "general": {
      "service_name": "Support RAG",
      "version": "1.0.0",
      "timezone": "UTC"
    },
    "retrieval": {
      "vector_db": "qdrant",
      "embedding_model": "all-MiniLM-L6-v2",
      "similarity_threshold": 0.4,
      "top_k": 5,
      "use_hybrid_search": true,
      "bm25_weight": 0.3,
      "vector_weight": 0.7
    },
    "generation": {
      "llm_model": "gpt-4o-mini",
      "temperature": 0.1,
      "max_tokens": 500
    },
    "cache": {
      "enabled": true,
      "ttl_seconds": 3600,
      "max_size_mb": 1000
    },
    "limits": {
      "max_query_length": 2000,
      "max_conversation_turns": 20,
      "query_timeout_seconds": 30,
      "batch_query_max_size": 100
    },
    "languages": {
      "supported": ["en", "ru", "de", "fr", "es"],
      "auto_translate": true
    }
  }
}
```

---

#### `PUT /api/v1/config` (Admin Only)
Update system configuration.

**Request:**
```json
{
  "retrieval": {
    "top_k": 7,
    "similarity_threshold": 0.5
  },
  "generation": {
    "temperature": 0.2
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "updated_fields": ["retrieval.top_k", "retrieval.similarity_threshold", "generation.temperature"],
    "changes_applied": true,
    "warning": "Configuration changed. Restart service for some changes to take effect."
  }
}
```

---

### 2. Intent & Category Management

#### `GET /api/v1/intents`
List all recognized intents (with embeddings for matching).

**Response:**
```json
{
  "status": "success",
  "data": {
    "intents": [
      {
        "intent_id": "intent_policy_info",
        "name": "Policy Information",
        "description": "Questions about company policies",
        "examples": [
          "What is your return policy?",
          "Tell me about shipping costs",
          "Do you offer discounts?"
        ],
        "category": "information",
        "escalation_weight": 0.1,
        "last_updated": "2026-01-05T00:00:00Z",
        "usage_count": 1250
      }
    ],
    "total": 24
  }
}
```

---

#### `POST /api/v1/intents`
Create a new intent.

**Request:**
```json
{
  "name": "Refund Status",
  "description": "Questions about refund status and processing",
  "examples": [
    "Where is my refund?",
    "How long do refunds take?",
    "Has my refund been processed?"
  ],
  "category": "status",
  "escalation_weight": 0.3
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "intent_id": "intent_refund_status",
    "name": "Refund Status",
    "created_at": "2026-01-07T10:18:00Z"
  }
}
```

---

#### `PUT /api/v1/intents/{intent_id}`
Update an intent.

**Request:**
```json
{
  "examples": [
    "Where is my refund?",
    "Refund tracking",
    "When will I get my money back?"
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "intent_id": "intent_refund_status",
    "embeddings_updated": true,
    "updated_at": "2026-01-07T10:18:30Z"
  }
}
```

---

#### `GET /api/v1/categories`
List all document categories.

**Response:**
```json
{
  "status": "success",
  "data": {
    "categories": [
      {
        "category_id": "returns",
        "name": "Returns & Refunds",
        "description": "Return policy, refund status, etc.",
        "document_count": 45,
        "qa_pair_count": 287,
        "parent_category": null,
        "subcategories": ["return_policy", "refund_status"]
      }
    ],
    "total": 12
  }
}
```

---

### 3. Model & Guardrail Management

#### `GET /api/v1/guardrails`
Get input/output guardrail rules.

**Response:**
```json
{
  "status": "success",
  "data": {
    "input_guardrails": {
      "enabled": true,
      "rules": [
        {
          "rule_id": "gr_profanity",
          "name": "Profanity Filter",
          "enabled": true,
          "severity": "high",
          "action": "block",
          "error_message": "Message contains inappropriate language"
        },
        {
          "rule_id": "gr_sql_injection",
          "name": "SQL Injection Detection",
          "enabled": true,
          "severity": "critical",
          "action": "block"
        }
      ]
    },
    "output_guardrails": {
      "enabled": true,
      "rules": [
        {
          "rule_id": "gr_pii",
          "name": "PII Detection",
          "enabled": true,
          "severity": "high",
          "action": "redact"
        }
      ]
    }
  }
}
```

---

#### `PUT /api/v1/guardrails/{rule_id}`
Enable/disable or update a guardrail rule.

**Request:**
```json
{
  "enabled": false,
  "action": "warn"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "rule_id": "gr_profanity",
    "enabled": false,
    "updated_at": "2026-01-07T10:19:00Z"
  }
}
```

---

## Session & Context API

### 1. Session Management

#### `POST /api/v1/sessions`
Create a new conversation session.

**Request:**
```json
{
  "user_id": "user_123",
  "metadata": {
    "source": "telegram",
    "device_id": "device_abc",
    "language": "en"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "session_id": "sess_xyz789",
    "user_id": "user_123",
    "created_at": "2026-01-07T10:20:00Z",
    "expires_at": "2026-01-08T10:20:00Z",
    "state": "active"
  }
}
```

---

#### `GET /api/v1/sessions/{session_id}`
Get session details and conversation history.

**Response:**
```json
{
  "status": "success",
  "data": {
    "session_id": "sess_xyz789",
    "user_id": "user_123",
    "created_at": "2026-01-07T10:20:00Z",
    "expires_at": "2026-01-08T10:20:00Z",
    "state": "active",
    "conversation_turns": 5,
    "messages": [
      {
        "message_id": "msg_001",
        "role": "user",
        "content": "What's your return policy?",
        "timestamp": "2026-01-07T10:21:00Z",
        "query_id": "q_abc123"
      },
      {
        "message_id": "msg_002",
        "role": "assistant",
        "content": "Our return policy allows returns within 30 days...",
        "timestamp": "2026-01-07T10:21:05Z"
      }
    ]
  }
}
```

---

#### `DELETE /api/v1/sessions/{session_id}`
End a session (soft delete, data retained for evaluation).

**Response:**
```json
{
  "status": "success",
  "data": {
    "session_id": "sess_xyz789",
    "state": "closed",
    "closed_at": "2026-01-07T10:25:00Z"
  }
}
```

---

### 2. User Profiles

#### `GET /api/v1/users/{user_id}`
Get user profile and interaction history.

**Response:**
```json
{
  "status": "success",
  "data": {
    "user_id": "user_123",
    "created_at": "2025-12-01T00:00:00Z",
    "total_queries": 47,
    "total_sessions": 12,
    "average_satisfaction": 4.5,
    "preferred_language": "en",
    "last_activity": "2026-01-07T10:25:00Z",
    "metadata": {
      "contact_email": "user@example.com",
      "phone": "+1234567890"
    }
  }
}
```

---

#### `PUT /api/v1/users/{user_id}`
Update user preferences.

**Request:**
```json
{
  "preferred_language": "ru",
  "metadata": {
    "contact_email": "newemail@example.com"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "user_id": "user_123",
    "updated_at": "2026-01-07T10:26:00Z"
  }
}
```

---

## Analytics & Monitoring API

### 1. Metrics & Statistics

#### `GET /api/v1/analytics/metrics`
Get real-time service metrics.

**Query Parameters:**
```
GET /api/v1/analytics/metrics?period=24h&resolution=1h
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "period": "24h",
    "data_points": [
      {
        "timestamp": "2026-01-07T09:00:00Z",
        "queries_total": 1250,
        "queries_auto_reply": 1050,
        "queries_escalated": 200,
        "average_response_time_ms": 245,
        "cache_hit_rate": 0.32,
        "satisfaction_score": 4.6,
        "availability": 0.99999
      }
    ],
    "summary": {
      "total_queries": 30000,
      "auto_reply_rate": 0.84,
      "escalation_rate": 0.16,
      "p50_response_time_ms": 180,
      "p95_response_time_ms": 450,
      "p99_response_time_ms": 780
    }
  }
}
```

---

#### `GET /api/v1/analytics/queries`
Analyze query patterns and trends.

**Query Parameters:**
```
GET /api/v1/analytics/queries?group_by=category&period=7d
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "grouping": "category",
    "period": "7d",
    "trends": [
      {
        "category": "returns",
        "query_count": 4500,
        "escalation_count": 200,
        "escalation_rate": 0.044,
        "avg_satisfaction": 4.7,
        "top_intents": [
          "policy_info",
          "refund_status"
        ]
      }
    ]
  }
}
```

---

#### `GET /api/v1/analytics/documents`
Get document usage statistics.

**Query Parameters:**
```
GET /api/v1/analytics/documents?sort=-retrieval_count&limit=20
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "documents": [
      {
        "document_id": "doc_001",
        "title": "Return Policy FAQ",
        "retrieval_count": 5420,
        "avg_relevance_score": 0.92,
        "user_satisfaction": 4.8,
        "last_updated": "2026-01-05T00:00:00Z"
      }
    ]
  }
}
```

---

### 2. Evaluation & Quality

#### `POST /api/v1/evaluation/ragas`
Run Ragas evaluation on a set of queries.

**Request:**
```json
{
  "dataset_id": "dataset_001",
  "query_ids": ["q_abc", "q_def", "q_ghi"],
  "metrics": ["context_precision", "context_recall", "faithfulness", "answer_relevancy"]
}
```

**Response:**
```json
{
  "status": "pending",
  "data": {
    "job_id": "job_eval_001",
    "status": "evaluating",
    "progress": 0.33
  }
}
```

---

#### `GET /api/v1/evaluation/results/{eval_id}`
Get evaluation results.

**Response:**
```json
{
  "status": "success",
  "data": {
    "eval_id": "eval_001",
    "dataset_id": "dataset_001",
    "metrics": {
      "context_precision": {
        "mean": 0.81,
        "std": 0.12,
        "min": 0.45,
        "max": 0.99
      },
      "context_recall": {
        "mean": 0.87,
        "std": 0.08
      },
      "faithfulness": {
        "mean": 0.93,
        "std": 0.05
      }
    },
    "per_query": [
      {
        "query_id": "q_abc",
        "context_precision": 0.88,
        "context_recall": 0.92,
        "faithfulness": 0.95
      }
    ]
  }
}
```

---

### 3. Logs & Traces

#### `GET /api/v1/logs`
Get system logs with filtering.

**Query Parameters:**
```
GET /api/v1/logs?level=ERROR&source=retrieval&limit=50&offset=0
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "logs": [
      {
        "timestamp": "2026-01-07T10:15:30Z",
        "level": "ERROR",
        "source": "retrieval.qdrant",
        "message": "Connection timeout",
        "request_id": "req_abc123",
        "trace_id": "trace_xyz789"
      }
    ],
    "total": 3,
    "pagination": {
      "limit": 50,
      "offset": 0,
      "total": 1250,
      "has_next": true
    }
  }
}
```

---

#### `GET /api/v1/traces/{trace_id}`
Get full execution trace (LangGraph + Langfuse integration).

**Response:**
```json
{
  "status": "success",
  "data": {
    "trace_id": "trace_xyz789",
    "query_id": "q_abc123",
    "total_duration_ms": 245,
    "nodes": [
      {
        "node_name": "input_guardrails",
        "duration_ms": 5,
        "status": "passed",
        "inputs": { "question": "What is..." },
        "outputs": { "guardrails_passed": true }
      },
      {
        "node_name": "retrieval",
        "duration_ms": 120,
        "status": "success",
        "inputs": { "question": "What is..." },
        "outputs": { "docs": [...], "scores": [...] }
      }
    ]
  }
}
```

---

## Webhook Specifications

### Overview

Webhooks enable **event-driven integration** with third-party systems. The service emits both:

1. **Incoming webhooks** — API clients can configure webhook URLs to receive events
2. **Outgoing webhooks** — Trigger external systems when certain events occur

---

### Webhook Event Types

#### Category: Query Events

| Event Type | Trigger | Payload |
|-----------|---------|---------|
| `query.submitted` | User submits a question | `{query_id, question, user_id, session_id}` |
| `query.completed` | Query processing finished | `{query_id, answer, confidence, sources}` |
| `query.escalated` | Query routed to human support | `{query_id, reason, escalation_category}` |
| `query.failed` | Query processing failed | `{query_id, error_code, error_message}` |

#### Category: Document Events

| Event Type | Trigger | Payload |
|-----------|---------|---------|
| `document.uploaded` | Document upload started | `{job_id, filename, size_bytes}` |
| `document.processing_started` | Document processing begins | `{job_id, files_count}` |
| `document.qa_extracted` | Q&A pairs extracted | `{job_id, qa_count, warnings}` |
| `document.ingested` | Document indexed in vector DB | `{job_id, qa_ingested, time_ms}` |
| `document.ingestion_failed` | Ingestion failed | `{job_id, error_code, error_message}` |
| `document.deleted` | Document archived | `{document_id, qa_archived}` |

#### Category: Job Events

| Event Type | Trigger | Payload |
|-----------|---------|---------|
| `job.started` | Job execution begins | `{job_id, job_type}` |
| `job.progress` | Job progresses (optional) | `{job_id, progress, eta_seconds}` |
| `job.completed` | Job finishes successfully | `{job_id, job_type, result}` |
| `job.failed` | Job fails | `{job_id, error_code, error_message}` |
| `job.cancelled` | Job cancelled by user | `{job_id, cancelled_by}` |

#### Category: Session Events

| Event Type | Trigger | Payload |
|-----------|---------|---------|
| `session.created` | New session started | `{session_id, user_id}` |
| `session.message` | Message added to session | `{session_id, message_id, content}` |
| `session.closed` | Session ended | `{session_id, turn_count, duration_ms}` |

#### Category: System Events

| Event Type | Trigger | Payload |
|-----------|---------|---------|
| `system.health_changed` | Service health status changed | `{status, affected_components}` |
| `system.config_updated` | Configuration changed | `{changed_fields, applied_at}` |
| `system.quota_exceeded` | Rate limit/quota exceeded | `{user_id, quota_type, limit}` |

---

### Webhook Request Format

**POST {callback_url}**

```json
{
  "event_type": "query.completed",
  "event_id": "evt_abc123xyz",
  "timestamp": "2026-01-07T10:16:00Z",
  "retry_count": 0,
  "data": {
    "query_id": "q_abc123",
    "question": "What's your return policy?",
    "answer": "We accept returns within 30 days...",
    "confidence": 0.92,
    "sources": [
      {
        "document_id": "doc_001",
        "title": "Return Policy FAQ",
        "relevance_score": 0.95
      }
    ],
    "user_id": "user_123",
    "session_id": "sess_xyz789"
  },
  "metadata": {
    "webhook_id": "whk_001",
    "delivery_attempt": 1,
    "signature": "sha256=abcd1234..."
  }
}
```

---

### Webhook Response & Retry Logic

**Expected Response:**
- Status: `200 OK` or `202 Accepted`
- Response body: `{"status": "received"}` (optional)

**Retry Policy:**
- **Initial delivery:** Immediate
- **Retry 1:** 5 seconds delay
- **Retry 2:** 30 seconds delay
- **Retry 3:** 5 minutes delay
- **Retry 4:** 30 minutes delay
- **Max retries:** 4
- **Timeout per attempt:** 10 seconds

**Failure Handling:**
- After max retries, event marked as `delivery_failed`
- Admin receives notification
- Event logged in `/api/v1/webhooks/failures` endpoint

---

### Webhook Registration & Management

#### `POST /api/v1/webhooks`
Register a webhook callback URL.

**Request:**
```json
{
  "url": "https://myapp.example.com/webhooks/supportrag",
  "events": [
    "query.completed",
    "query.escalated",
    "document.ingested"
  ],
  "active": true,
  "headers": {
    "Authorization": "Bearer webhook_secret_xyz",
    "X-Custom-Header": "value"
  },
  "retry_policy": {
    "max_retries": 4,
    "timeout_seconds": 10
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "webhook_id": "whk_001",
    "url": "https://myapp.example.com/webhooks/supportrag",
    "events": ["query.completed", "query.escalated", "document.ingested"],
    "active": true,
    "created_at": "2026-01-07T10:20:00Z",
    "test_url": "/api/v1/webhooks/whk_001/test"
  }
}
```

---

#### `GET /api/v1/webhooks`
List all registered webhooks.

**Response:**
```json
{
  "status": "success",
  "data": {
    "webhooks": [
      {
        "webhook_id": "whk_001",
        "url": "https://myapp.example.com/webhooks/supportrag",
        "events": ["query.completed", "query.escalated"],
        "active": true,
        "created_at": "2026-01-07T10:20:00Z",
        "last_delivery": {
          "timestamp": "2026-01-07T10:25:00Z",
          "status": "success"
        },
        "stats": {
          "total_deliveries": 4250,
          "successful": 4235,
          "failed": 15,
          "success_rate": 0.9965
        }
      }
    ]
  }
}
```

---

#### `PUT /api/v1/webhooks/{webhook_id}`
Update webhook configuration.

**Request:**
```json
{
  "active": false,
  "events": ["query.completed", "document.ingested"]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "webhook_id": "whk_001",
    "updated_at": "2026-01-07T10:30:00Z"
  }
}
```

---

#### `DELETE /api/v1/webhooks/{webhook_id}`
Delete a webhook.

**Response:**
```json
{
  "status": "success",
  "data": {
    "webhook_id": "whk_001",
    "deleted_at": "2026-01-07T10:30:30Z"
  }
}
```

---

#### `POST /api/v1/webhooks/{webhook_id}/test`
Send a test webhook event.

**Response:**
```json
{
  "status": "success",
  "data": {
    "webhook_id": "whk_001",
    "test_event_id": "evt_test_001",
    "delivery": {
      "status": "success",
      "response_code": 200,
      "response_time_ms": 245
    }
  }
}
```

---

#### `GET /api/v1/webhooks/deliveries`
Get webhook delivery history.

**Query Parameters:**
```
GET /api/v1/webhooks/deliveries?webhook_id=whk_001&status=failed&limit=20
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "deliveries": [
      {
        "delivery_id": "del_001",
        "webhook_id": "whk_001",
        "event_id": "evt_abc123",
        "event_type": "query.completed",
        "status": "success",
        "response_code": 200,
        "response_time_ms": 185,
        "timestamp": "2026-01-07T10:16:00Z"
      }
    ],
    "total": 4250
  }
}
```

---

#### `GET /api/v1/webhooks/failures`
Get failed webhook deliveries (for debugging).

**Response:**
```json
{
  "status": "success",
  "data": {
    "failures": [
      {
        "webhook_id": "whk_001",
        "event_id": "evt_xyz789",
        "event_type": "document.ingested",
        "last_error": "Connection timeout",
        "retry_count": 4,
        "failed_at": "2026-01-07T10:15:00Z",
        "action": "manual_retry_required"
      }
    ],
    "total": 5
  }
}
```

---

## Error Handling

### Standard Error Response Format

```json
{
  "status": "error",
  "data": null,
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "message": "Question too long (max 2000 characters)",
      "field": "question",
      "details": {
        "max_length": 2000,
        "provided_length": 2150
      }
    }
  ],
  "meta": {
    "request_id": "req_abc123xyz",
    "timestamp": "2026-01-07T10:16:00Z",
    "trace_id": "trace_xyz789"
  }
}
```

---

### Error Codes

| HTTP | Code | Description | Retry? |
|------|------|-------------|--------|
| 400 | `VALIDATION_ERROR` | Invalid input format | No |
| 400 | `QUERY_TOO_LONG` | Query exceeds max length | No |
| 400 | `INVALID_FORMAT` | Unsupported document format | No |
| 401 | `UNAUTHORIZED` | Missing/invalid API key | No |
| 403 | `FORBIDDEN` | Insufficient permissions | No |
| 404 | `NOT_FOUND` | Resource doesn't exist | No |
| 409 | `CONFLICT` | Resource already exists | No |
| 429 | `RATE_LIMIT_EXCEEDED` | Quota exceeded | Yes (with backoff) |
| 500 | `INTERNAL_ERROR` | Server error | Yes (with backoff) |
| 503 | `SERVICE_UNAVAILABLE` | Database/service down | Yes (with exponential backoff) |
| 504 | `GATEWAY_TIMEOUT` | Request timeout | Yes |

---

## Rate Limiting & Quotas

### Rate Limit Headers

All responses include:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 987
X-RateLimit-Reset: 1641591300
X-RateLimit-Retry-After: 60
```

### Limits by Endpoint Tier

| Tier | Queries/min | Uploads/day | Batch Size |
|------|------------|-------------|-----------|
| **Free** | 10 | 10 | 5 |
| **Pro** | 100 | 100 | 50 |
| **Enterprise** | Unlimited | Unlimited | 1000 |

### Quota Policies

- **Soft limit:** Warning header, request still succeeds
- **Hard limit:** `429 Too Many Requests` response
- **Burst:** Allow 20% spike above limit for 60 seconds
- **Reset:** Hourly (sliding window)

---

## Security & Authentication

### Authentication Methods

#### 1. API Key (Simple)
```
Authorization: Bearer sk_live_abc123xyz
```

#### 2. OAuth 2.0 (Recommended for Apps)
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

#### 3. HMAC Signature (for Webhooks)
```
X-Signature: sha256={base64(HMAC-SHA256(payload, secret))}
```

---

### Headers

**Required:**
```
Authorization: Bearer {api_key}
Content-Type: application/json
Accept: application/vnd.supportrag.v1+json
```

**Optional:**
```
X-Request-ID: {idempotency_key}
X-Client-Version: {client_version}
X-Tenant-ID: {tenant_id}  # For multi-tenant deployments
```

---

### Security Best Practices

1. **Never log sensitive data:** Passwords, API keys, PII
2. **Use HTTPS only:** TLS 1.3+
3. **Validate webhook signatures:** Verify `X-Signature` header
4. **Implement idempotency:** Use `X-Request-ID` for retries
5. **Rotate API keys regularly:** Min every 90 days
6. **Use scoped tokens:** Separate read/write/admin keys

---

## Backwards Compatibility

### Versioning Strategy

**Current:** `v1` (stable)
**Deprecated:** None yet
**Upcoming:** `v2` (design phase)

### Deprecation Timeline

- **Announcement:** 6 months notice
- **Parallel support:** Both old + new versions work
- **Final sunset:** 6 months after announcement
- **Breaking changes:** Only in major versions

### Example: Supporting Multiple Versions

```
GET /api/v1/queries         # v1 (old format)
GET /api/v2/queries         # v2 (new format)
Accept: application/vnd.supportrag.v1+json  # Version negotiation
```

---

## Summary: API Governance

| Aspect | Policy |
|--------|--------|
| **Versioning** | URL-path + Header-based |
| **Pagination** | limit/offset with cursor support |
| **Async ops** | Job IDs + webhooks for polling |
| **Errors** | Standard envelope with detailed codes |
| **Rate limits** | Per-tier quotas, sliding window |
| **Security** | API key + OAuth + HMAC signatures |
| **Monitoring** | Request IDs + trace IDs for all requests |
| **SLA** | 99.9% uptime, <500ms p95 latency |

---

## Appendix: SDK Examples

### Python SDK (Official)

```python
from supportrag import Client

client = Client(api_key="sk_live_abc123xyz")

# Simple query
response = client.queries.create(
    question="What's your return policy?",
    user_id="user_123"
)
print(response.answer)
print(response.sources)

# With conversation history
response = client.queries.create(
    question="Can I extend the return period?",
    conversation_history=[
        {"role": "user", "content": "What's your return policy?"},
        {"role": "assistant", "content": "..."}
    ],
    user_id="user_123",
    session_id="sess_xyz789"
)

# Upload documents
job = client.documents.upload(
    files=["faq.pdf"],
    metadata={"category": "faq"}
)
job.wait()  # Poll until complete
print(f"Ingested {job.result.qa_pairs_ingested} Q&A pairs")

# Subscribe to webhooks
client.webhooks.register(
    url="https://myapp.example.com/webhooks/supportrag",
    events=["query.completed", "query.escalated"]
)
```

### JavaScript/TypeScript SDK

```typescript
import { SupportRAGClient } from '@supportrag/js';

const client = new SupportRAGClient({
  apiKey: 'sk_live_abc123xyz'
});

// Simple query
const response = await client.queries.create({
  question: "What's your return policy?",
  userId: "user_123"
});
console.log(response.answer);

// Batch queries
const job = await client.queries.batch([
  { question: "Return policy?" },
  { question: "Shipping cost?" }
]);
job.on('completed', (result) => {
  console.log('All queries done:', result);
});

// Document ingestion with callback
const uploadJob = await client.documents.upload({
  files: [file1, file2],
  callbackUrl: 'https://myapp.example.com/webhook'
});
```

---

**Document Version:** API_DESIGN_v1.0
**Last Updated:** 2026-01-07
**Next Review:** 2026-04-07
