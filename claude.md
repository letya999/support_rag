# Support RAG - Production Multi-Language Q&A Pipeline

A modular, production-grade Retrieval-Augmented Generation system for answering customer support questions strictly from provided Q&A documents. Built with LangGraph, PostgreSQL+pgvector, and comprehensive safety guardrails.

## Project Overview

**What it does:** Answers support queries using RAG with groundedness guarantees, caching, multi-turn conversation context, and Telegram bot integration. Pipeline executes 22-node LangGraph workflow per query: guardrails → search → ranking → generation → output validation.

**Core principle:** Answers ONLY from retrieved context. Escalates to humans when knowledge gaps exist.

## Architecture

### LangGraph Pipeline (22 Nodes)
```
Input → InputGuardrails → CacheCheck → LanguageDetection → DialogAnalysis
 → QueryAggregation → QueryTranslation → EasyClassification → MetadataFiltering
 → HybridSearch (vector+lexical) → Reranking → MultiHopReasoning
 → Fusion → StateDecision → Routing → PromptSelection
 → Generation (gpt-4o-mini) → OutputGuardrails → ArchiveSession → CacheStore
```

Each node has isolated `config.yaml` (auto-merged into `pipeline_config.yaml`).

### Storage Layer
- **PostgreSQL (pgvector):** Q&A documents + vector embeddings + metadata (category, intent, language)
- **Qdrant:** Semantic similarity search
- **Redis:** Query→Answer caching with TTL
- **Docker:** Multi-service orchestration (postgres, redis, qdrant, fastapi)

### Key Components
- **Retrieval:** Hybrid search (vector + BM25), multi-hop, reranking, fusion
- **Safety:** Input guardrails (content blocking), output guardrails (response validation)
- **Classification:** FastText-based (fast) + semantic (embeddings-based)
- **Context:** User profiles, multi-turn conversation history, session state machine
- **Multi-language:** Query translation, language detection, multilingual embeddings
- **Performance:** Model warmup on startup, Redis caching, semantic cache for similar queries
- **Monitoring:** Langfuse tracing + RAGAS evaluation metrics

## Tech Stack
- **Framework:** LangGraph ≥1.0.5, LangChain ≥1.2.0
- **API:** FastAPI ≥0.128.0, Uvicorn
- **LLM:** OpenAI (gpt-4o-mini), sentence-transformers embeddings
- **Databases:** PostgreSQL+pgvector, Qdrant, Redis
- **Evaluation:** Langfuse ≥3.11.2, RAGAS ≥0.2.14
- **ML:** PyTorch, scikit-learn, llm-guard, FastText
- **Document processing:** PyPDF, python-docx, pandas

## Development Commands

### Setup
```bash
pip install -r requirements.txt
docker-compose up -d          # Start all services
```

### API & Pipeline
```bash
uvicorn app.main:app --reload # Start FastAPI (auto-warmup)
curl "http://localhost:8000/ask?q=How%20to%20reset%20password"
curl -X POST http://localhost:8000/rag/query -H "Content-Type: application/json" \
  -d '{"question":"...", "conversation_history":[], "user_id":"...", "session_id":"..."}'
```

### Data Ingestion
```bash
# Upload documents → Auto-extract Q&A → Review metadata → Ingest
python scripts/ingest.py --file datasets/qa_data.json

# Generate synthetic Q&A
python scripts/generate_synthetic_qa.py --count 1000 --output datasets/qa_synthetic.json
python scripts/generate_qa_from_product.py --product-name "..." --description "..." --count 500
python scripts/generate_qa_from_faq.py --faq-file datasets/faq.json --count 1000
```

### Configuration & Management
```bash
python scripts/rebuild_pipeline_config.py  # Merge node configs → pipeline_config.yaml
python scripts/refresh_intents.py          # Update intent registry
curl http://localhost:8000/admin/intents-registry  # View intents
curl -X POST http://localhost:8000/config/reload   # Hot-reload config
```

### Testing & Evaluation
```bash
pytest                              # Run test suite
python evaluate_retrieval.py        # RAGAS evaluation (precision, recall, faithfulness)
python scripts/bench_modular.py     # Performance benchmarking
python scripts/test_api_metadata.py # Test metadata endpoints
python scripts/reset_db.py          # Clear all databases
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/ask?q=...` | GET | RAG query (simple) |
| `/rag/query` | POST | RAG with history (Telegram bot) |
| `/search?q=...` | GET | Raw document search |
| `/documents/upload` | POST | Upload PDF/DOCX/CSV |
| `/documents/confirm` | POST | Ingest uploaded Q&A |
| `/documents/metadata-generation/analyze` | POST | Auto-classify Q&A |
| `/documents/metadata-generation/review` | POST | Correct metadata |
| `/documents/metadata-generation/confirm` | POST | Ingest classified Q&A |
| `/config/system-phrases` | GET | System config |
| `/config/languages` | GET | Language config |
| `/config/reload` | POST | Hot-reload configs |
| `/admin/intents-registry` | GET | View intents |
| `/admin/refresh-intents` | POST | Refresh intents |

## Configuration Structure

**Core configs** (YAML-based):
- `.env` — OpenAI key, DB credentials, Langfuse keys
- `pipeline_order.yaml` — Node execution sequence
- `pipeline_config.yaml` — **Auto-generated**, merged from all node configs
- `app/nodes/_shared_config/intents_registry.yaml` — Categories & intents mapping
- `config/product_configs_examples.yaml` — Per-product configurations

Each node in `app/nodes/{node_name}/config.yaml` has isolated settings (merged by `rebuild_pipeline_config.py`).

## Data Format

**Q&A JSON Structure:**
```json
{
  "id": "uuid",
  "question": "...",
  "answer": "...",
  "metadata": {
    "category": "...",
    "intent": "...",
    "language": "en",
    "confidence": 0.95,
    "source": "..."
  }
}
```

**Pre-generated Datasets:** 1000+ Q&A pairs with evaluation sets, ground truth, synthetic variants.

## Evaluation & Monitoring

- **RAGAS Metrics:** Context precision, context recall, faithfulness
- **Langfuse Tracing:** All 22 pipeline nodes traced with detailed spans
- **Trace Files:** JSON exports from Langfuse for post-analysis
- **Eval Datasets:** Ground truth variants (adversarial, synonym-based)

## Key Features

✓ Hybrid search (vector + lexical ranking)
✓ Multi-hop reasoning for complex queries
✓ Result reranking & fusion
✓ Input/output safety guardrails
✓ Multi-language support (detection + translation)
✓ Redis caching (with semantic similarity)
✓ Session & conversation context
✓ Metadata-based filtering (category, intent)
✓ Handoff/escalation logic
✓ Telegram bot integration
✓ Hot-reload configuration
✓ Production monitoring (Langfuse)
✓ Document ingestion (PDF, DOCX, CSV, JSON)

## Important Notes

- **Configuration Priority:** Node-level configs → merged into pipeline_config.yaml → runtime
- **Pipeline as Code:** Nodes are modular; edit node `config.yaml` + rebuild with `rebuild_pipeline_config.py`
- **Safety First:** Guardrails execute early (before cache); invalid outputs rejected
- **Groundedness:** LLM instructed to answer ONLY from retrieved context or escalate
- **Performance:** Model warmup on startup; model weights loaded once, used across requests
- **Git:** Develop on `claude/write-claude-md-bDuB2`, commit with clear messages, push to branch

## Useful Locations

- **Nodes:** `app/nodes/` (23 modular workflow steps)
- **API:** `app/api/` (FastAPI routes)
- **Services:** `app/services/` (ingestion, metadata, search logic)
- **Pipeline:** `app/pipeline/` (LangGraph state + execution)
- **Storage:** `app/storage/` (database interfaces)
- **Datasets:** `datasets/` (pre-generated Q&A pairs + eval sets)
- **Scripts:** `scripts/` (20+ utilities: generation, ingestion, benchmarking)