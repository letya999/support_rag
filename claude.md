# Support RAG - Production Q&A Pipeline

Production-grade Retrieval-Augmented Generation system for customer support. Answers ONLY from retrieved context with LangGraph 22-node pipeline, PostgreSQL+pgvector, Qdrant, Redis. Built with groundedness guarantees, multi-turn conversations, and Telegram integration.

**Core Principle:** Answer from context or escalate to humans. Never hallucinate.

## Tech Stack

**Framework:** LangGraph ≥1.0.5, LangChain ≥1.2.0, FastAPI ≥0.128.0  
**LLM:** OpenAI gpt-4o-mini, sentence-transformers embeddings  
**Storage:** PostgreSQL+pgvector (docs+metadata), Qdrant (vectors), Redis (cache+staging)  
**ML/NLP:** PyTorch, FastText, llm-guard, RAGAS, Langfuse  
**Docs:** PyPDF, python-docx, pandas (CSV/JSON/PDF/DOCX)

## Architecture

### LangGraph Pipeline (22 Nodes)
```
Input → InputGuardrails → CacheCheck → LanguageDetection → DialogAnalysis
 → QueryAggregation → QueryTranslation → EasyClassification → MetadataFiltering
 → HybridSearch → Reranking → MultiHopReasoning → Fusion → StateDecision
 → Routing → PromptSelection → Generation → OutputGuardrails → ArchiveSession → CacheStore
```

Each node has isolated `config.yaml` → auto-merged into `pipeline_config.yaml`.

### API Structure (`/api/v1`)

**Envelope Pattern** (all responses):
```json
{
  "data": { ... },
  "error": null,
  "meta": {
    "trace_id": "uuid",
    "request_id": "uuid",
    "pagination": { "limit": 50, "offset": 0, "total": 100 }
  }
}
```

**11 API Groups:**
1. **Chat** - RAG completions (sync + SSE stream)
2. **Ingestion** - Document upload → staging → commit workflow
3. **Autoclassify** - LLM discovery, zero-shot, batch classification
4. **Taxonomy** - Categories & intents management
5. **Channels** - Telegram/messaging integration
6. **History** - Message history from DB
7. **Cache** - Session state, recent messages, Redis metrics
8. **Chunks** - CRUD operations on knowledge base
9. **Dataset** - Generate eval datasets (simple/ground-truth)
10. **Config** - System config, pipeline refresh
11. **System** - Health checks, ping

### Storage Layer

**Staging Area Pattern (Redis → Postgres+Qdrant):**
1. Upload file → Draft created in Redis
2. Auto-extract Q&A pairs
3. Auto-classify (categories + intents)
4. User reviews & edits
5. Commit → Save to Postgres + Qdrant + embeddings

**Why Staging?** Allows review before indexing, prevents bad data pollution, supports batch edits.

## Key Features

### Retrieval
✓ Hybrid search (vector + BM25 lexical)  
✓ Multi-hop reasoning for complex queries  
✓ Result reranking & fusion  
✓ Metadata filtering (category, intent, language)

### Safety & Guardrails
✓ Input guardrails (content blocking, validation)  
✓ Output guardrails (groundedness check)  
✓ LLM instructed: answer from context or say "I don't know"  
✓ Escalation to humans when uncertain

### Classification (3 Modes)

**1. Discovery (LLM-based):**
- Auto-clusters chunks, generates category/intent names
- Use for exploring new data

**2. Zero-shot (semantic similarity):**
- Classifies against existing system taxonomy
- No LLM needed, fast

**3. Custom Taxonomy (batch):**
- Batch classification with custom categories/intents
- Flexible for specific use cases

### Multi-language
✓ Query translation  
✓ Language detection  
✓ Multilingual embeddings  
✓ Response translation

### Context Management
✓ Multi-turn conversation history  
✓ Session state machine  
✓ Clarification loop (if doc has `clarifying_questions`)  
✓ User profiles

### Performance
✓ Model warmup on startup  
✓ Redis query→answer caching (TTL)  
✓ Semantic cache (similar queries)  
✓ Connection pooling

### Monitoring
✓ Langfuse tracing (all 22 nodes)  
✓ RAGAS metrics (precision, recall, faithfulness)  
✓ Structured logging with filtered sensitive data

## Project Structure

```
support_rag/
├── app/
│   ├── api/v1/           # FastAPI endpoints (11 modules)
│   ├── nodes/            # 22 LangGraph pipeline nodes
│   ├── services/         # Business logic
│   │   ├── classification/      # Discovery, zero-shot services
│   │   ├── document_loaders/    # CSV, JSON, PDF, DOCX
│   │   ├── qa_extractors/       # Q&A extraction
│   │   ├── metadata_generation/ # Auto-classification
│   │   ├── cache/              # Redis cache manager
│   │   └── staging.py          # Staging area service
│   ├── pipeline/         # LangGraph state + execution
│   ├── storage/          # DB interfaces (Postgres, Qdrant, Redis)
│   └── integrations/     # Telegram bot
├── datasets/             # Pre-generated Q&A + eval sets
├── scripts/              # 20+ utilities (ingest, generate, benchmark)
└── docker-compose.yml    # Postgres + Redis + Qdrant
```

## Development Workflow

### Quick Start
```bash
# 1. Setup
pip install -r requirements.txt
docker-compose up -d               # Start Postgres, Redis, Qdrant

# 2. Run API
uvicorn app.main:app --reload

# 3. View docs
open http://localhost:8000/docs    # Swagger UI
open http://localhost:8000/redoc   # ReDoc
```

### Common Commands
```bash
# Upload document → staging
curl -X POST http://localhost:8000/api/v1/ingestion/upload -F "file=@qa.json"

# Auto-classify draft (zero-shot)
curl -X POST http://localhost:8000/api/v1/autoclassify/{draft_id}/zeroshot

# Commit staging → production
curl -X POST http://localhost:8000/api/v1/ingestion/commit -d '{"draft_id": "..."}'

# RAG query
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"question": "How to reset password?", "user_id": "user123"}'

# Health check
curl http://localhost:8000/api/v1/health
```

### Data Ingestion Scripts
```bash
# Direct ingestion (bypasses staging)
python scripts/ingest.py --file datasets/qa_data.json

# Generate synthetic Q&A
python scripts/generate_synthetic_qa.py --count 1000

# Remove duplicates
python scripts/remove_duplicates.py

# Load test
python scripts/load_test.py --requests 100
```

## Important Rules & Conventions

### Configuration
- **Node configs:** Each node has `app/nodes/{node}/config.yaml`
- **Pipeline config:** Auto-generated by merging all node configs
- **Rebuild config:** Run when node configs change (not auto-reload)
- **Hot-reload:** Use `POST /api/v1/config/refresh` for runtime reload

### Code Organization
- **No direct DB queries in API routes:** Use services
- **Services are stateless:** Dependencies injected via functions
- **Pydantic models:** All request/response schemas
- **Envelope pattern:** All API responses wrapped in `Envelope[T]`

### Data Flow
```
Upload → Redis Draft → Review/Edit → Commit → Postgres + Qdrant
                ↓
         Auto-classify (optional)
                ↓
         Group by Category → Intent
```

### Testing & Evaluation
```bash
pytest                          # Run test suite
python evaluate_retrieval.py   # RAGAS evaluation
python scripts/bench_modular.py # Performance benchmark
```

### Taxonomy Management
- **Source of truth:** PostgreSQL `documents` table metadata
- **Registry file:** `app/_shared_config/intents_registry.yaml` (generated from DB)
- **Sync:** `POST /api/v1/categories/sync` regenerates registry from DB
- **Never edit YAML directly:** Always edit via DB or API

## Q&A Document Format

```json
{
  "id": "uuid",
  "question": "How to reset password?",
  "answer": "Go to Settings → Security → Reset Password...",
  "metadata": {
    "category": "Account Management",
    "intent": "password_reset",
    "language": "en",
    "confidence": 0.95,
    "source": "manual_upload",
    "requires_handoff": false,
    "clarifying_questions": ["Do you remember your email?"]
  }
}
```

**Clarifying Questions Flow:**  
If document has `clarifying_questions` → system enters `NEEDS_CLARIFICATION` state → asks questions → collects answers → retrieves refined results.

## Production Checklist

### Security
- [x] Input/output guardrails
- [x] Content filtering
- [x] Rate limiting (via middleware)
- [x] Request ID tracing

### Performance
- [x] Model warmup on startup
- [x] Connection pooling (Postgres, Redis)
- [x] Redis caching (query→answer)
- [x] Semantic cache (similar queries)

### Reliability
- [x] Graceful degradation (if Redis down → no cache)
- [x] Health checks (`/api/v1/health`)
- [x] Session persistence (Redis)
- [x] Retry logic (classification, search)

### Observability
- [x] Langfuse tracing (all 22 nodes)
- [x] Structured logging
- [x] Error tracking
- [x] RAGAS evaluation metrics

## Key Design Decisions

**Why LangGraph?** Modular, debuggable, supports complex state machines (clarification loop, multi-hop).

**Why Staging Area?** Prevents bad data pollution, allows batch review, supports iterative refinement.

**Why 3 Classification Modes?** Different use cases: Discovery (explore), Zero-shot (fast), Custom (flexible).

**Why Hybrid Search?** Combines semantic (vector) + lexical (BM25) for best recall.

**Why Redis for Staging?** Fast, ephemeral, supports TTL for auto-cleanup, no schema migrations.

**Why Qdrant + Postgres?** Qdrant for fast vector search, Postgres for reliable document storage + metadata queries.

## Common Pitfalls

❌ **Don't** edit `pipeline_config.yaml` directly → Edit node configs instead  
❌ **Don't** edit `intents_registry.yaml` → Sync from DB instead  
❌ **Don't** commit drafts without review → Use staging workflow  
❌ **Don't** skip auto-classification → Improves retrieval accuracy  
❌ **Don't** ignore health checks → Monitor Redis/Postgres/Qdrant status  

✅ **Do** use staging area for all uploads  
✅ **Do** review auto-classifications before commit  
✅ **Do** use zero-shot for known taxonomies  
✅ **Do** use discovery for new data exploration  
✅ **Do** monitor Langfuse traces for debugging  

## Troubleshooting

**High latency (>5s)?**
- Check Redis cache hit rate (`GET /api/v1/cache/status`)
- Check Qdrant performance (index size)
- Review Langfuse traces (which node is slow?)

**Classification errors?**
- Verify taxonomy sync: `POST /api/v1/categories/sync`
- Check embedding quality (are docs too short?)
- Try different classification mode

**Empty search results?**
- Check if documents are committed (not just in staging)
- Verify embeddings are generated
- Check metadata filters (too restrictive?)

**Session not persisting?**
- Verify Redis is running: `GET /api/v1/cache/status`
- Check session TTL config (default: 2 hours)
- Review user_id consistency across requests

## Documentation

- **`API_ENDPOINTS.md`** - Full API reference with examples
- **`DOCUMENTATION_INDEX.md`** - Navigation guide for all docs
- **`/docs`** - Interactive Swagger UI
- **`/redoc`** - Alternative API documentation

---

**Last Updated:** 2026-01-12  
**Version:** 1.0.0  
**API Version:** v1