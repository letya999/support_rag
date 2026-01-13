# Database Schema

Support RAG uses PostgreSQL as its primary relational store and vector engine (via `pgvector`).

## 🗄️ Relational Schema (PostgreSQL)

### 1. Knowledge Base
- **`documents`**: Primary table for indexed knowledge.
  - `id` (SERIAL, PK): Unique document ID.
  - `content` (TEXT): The actual text content.
  - `embedding` (vector(384)): Embedding for vector search.
  - `metadata` (JSONB): Flexible storage for category, source, tags, etc.
  - `search_vector` (tsvector): Generated column for full-text search.

### 2. Conversations & Sessions
- **`sessions_archive`**: Metadata about completed chat sessions.
  - `session_id` (PK): Unique session identifier.
  - `user_id`: Reference to user.
  - `outcome`: 'resolved', 'escalated', or 'abandoned'.
  - `metrics` (JSONB): Storage for latency, token count, etc.
- **`session_summaries`**: LLM-generated summaries for long-term context.
- **`user_profiles`**: Persistent user data and memory.

### 3. Messaging & Identity
- **`identities`**: Maps external IDs (e.g., Telegram ID) to internal user IDs.
- **`messages`**: Full history of user/assistant interactions if persistence is enabled.

### 4. Webhooks
- **`webhooks`**: Registry of active webhook subscriptions.
  - `webhook_id` (PK)
  - `url`: Target delivery URL.
  - `events`: Array of strings (`chat.response.generated`, etc.).
  - `secret_hash`: HMAC secret key.
- **`webhook_deliveries`**: Log of all sent webhooks and their statuses.

## 🔍 Vector Schema (Qdrant)

While PostgreSQL stores the source of truth, **Qdrant** is used for high-speed vector indexing.

- **Collection**: `documents`
  - **Vector Size**: 384 (default, fits `all-MiniLM-L6-v2`)
  - **Distance**: Cosine
  - **Payload**: Includes redundant `id`, `category`, and `intent` for fast server-side filtering.

## ⚡ Cache Layer (Redis)

- **Rate Limiting**: Uses `fastapi-limiter` patterns.
- **Semantic Cache**:
  - Key: `cache:{query_hash}`
  - Value: JSON containing the answer and source IDs.
- **Session Data**: Temporary storage for the active pipeline `State` during multi-turn loops.
