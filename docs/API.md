# REST API Documentation

The Support RAG API follows RESTful principles and returns standardized JSON responses wrapped in an `Envelope`.

## 📦 Base Configuration

- **Base URL**: `http://localhost:8000/api/v1`
- **Content-Type**: `application/json`

### Standard Response Envelope

```json
{
  "data": { ... },
  "meta": {
    "trace_id": "uuid-string"
  }
}
```

## 💬 Chat & RAG Endpoints

### POST `/chat/completions`
Executes a RAG query and returns a full synthesized answer.

**Request Body:**
```json
{
  "question": "How do I reset my password?",
  "session_id": "optional-uuid",
  "user_id": "optional-user-id",
  "conversation_history": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help?"}
  ],
  "user_metadata": { "platform": "web" }
}
```

**Successful Response (200):**
```json
{
  "data": {
    "question": "...",
    "answer": "To reset your password, visit...",
    "sources": [
      {
        "document_id": "123",
        "title": "Account FAQ",
        "relevance": 0.95
      }
    ],
    "confidence": 0.92
  }
}
```

---

### POST `/chat/stream`
Same as completions, but streams the response as Server-Sent Events (SSE).

**Events:**
- Token chunks: `data: {"token": "next_word"}`
- Final data: `data: {"final_data": { ... }}`
- Done signal: `data: {"token": "[DONE]"}`

---

## 📥 Ingestion & Knowledge Base

### POST `/ingestion/upload`
Uploads a file (PDF, JSON, DOCX, CSV, MD) and creates a staging draft.

**Form Data:**
- `file`: The document file to upload.

**Response:**
```json
{
  "data": {
    "draft_id": "draft-uuid",
    "filename": "faq.pdf",
    "total_pairs": 42
  }
}
```

---

### POST `/ingestion/commit`
Indexes a specific staging draft into the production search index (PostgreSQL + Qdrant).

**Request Body:**
```json
{
  "draft_id": "draft-uuid"
}
```

---

## ⚙️ System & Health

### GET `/system/health`
Returns the status of all backend services (DB, Redis, Qdrant).

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "redis": "connected",
    "qdrant": "connected"
  }
}
```
