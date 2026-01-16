# 📋 E2E & Contract Testing Plan - Support RAG

Комплексный план тестирования пайплайна Support RAG системы с использованием контрактных тестов и end-to-end сценариев.

---

## 📌 Оглавление

1. [Обзор](#обзор)
2. [Контрактные Тесты](#контрактные-тесты)
3. [E2E Тесты](#e2e-тесты)
4. [Структура Тестовых Файлов](#структура-тестовых-файлов)
5. [Ключевые Сценарии по Компонентам](#ключевые-сценарии-по-компонентам)
6. [Команды Запуска](#команды-запуска)
7. [Fixtures & Test Data](#fixtures--test-data)
8. [Метрики Успеха](#метрики-успеха)

---

## Обзор

### Цель
Разработать набор контрактных и E2E тестов для проверки:
- ✅ Что весь пайплайн работает корректно
- ✅ Что никогда ничего не сломается без срабатывания тестов
- ✅ Что компоненты соответствуют своим контрактам
- ✅ Что реальные сценарии пользователей работают

### Типы Тестов

| Тип | Фокус | Скорость | Количество |
|-----|-------|----------|-----------|
| **Contract** | Интерфейсы между компонентами | Быстрые | ~20 |
| **E2E Scenarios** | Реальные user flows | Средние | ~10 |
| **Error Cases** | Edge cases и отказы | Средние | ~10 |
| **Performance** | Latency & throughput | Медленные | ~3 |
| **TOTAL** | | | **~43 тестов** |

---

## Контрактные Тесты

### A. API Контракты (`tests/contracts/api/`)

#### `test_chat_completions_contract.py`
Проверяет соглашение для основного API endpoint.

```python
✅ Valid request → 200 + valid response structure
✅ Missing required field → 400 + error message
✅ Invalid message format → 422 validation error
✅ Response includes metadata (sources, confidence, processing_time)
✅ Response follows OpenAI-compatible schema
✅ Response format:
   {
     "id": "chatcmpl-...",
     "object": "chat.completion",
     "created": 1234567890,
     "model": "support-rag",
     "choices": [{
       "index": 0,
       "message": {
         "role": "assistant",
         "content": "..."
       },
       "finish_reason": "stop"
     }],
     "usage": {
       "prompt_tokens": 10,
       "completion_tokens": 50,
       "total_tokens": 60
     },
     "metadata": {
       "sources": [...],
       "confidence": 0.95,
       "processing_time_ms": 450,
       "session_id": "sess-..."
     }
   }
```

#### `test_analysis_endpoint_contract.py`
Проверяет `/api/v1/analysis` endpoint для классификации.

```python
✅ POST /api/v1/analysis with valid query → 200
✅ Returns: {category, intent, confidence, language}
✅ Confidence score in range [0, 1]
✅ Invalid input → 400
✅ Response schema:
   {
     "intent": "billing",
     "category": "question",
     "confidence": 0.87,
     "language": "en"
   }
```

#### `test_ingestion_endpoint_contract.py`
Проверяет загрузку документов.

```python
✅ POST with file → returns {document_id, status, chunks_count}
✅ Supported formats: PDF, DOCX, TXT, CSV
✅ Unsupported format → 400
✅ File size validation (max 50MB)
✅ Response schema:
   {
     "document_id": "doc-123",
     "filename": "document.pdf",
     "status": "indexed",
     "chunks_count": 42,
     "size_bytes": 245000,
     "indexed_at": "2026-01-16T10:30:00Z"
   }
```

#### `test_cache_endpoint_contract.py`
Проверяет управление кэшем.

```python
✅ GET /api/v1/cache/{query_hash} → cached response or 404
✅ DELETE /api/v1/cache/{query_hash} → 204
✅ Cache structure:
   {
     "query": "...",
     "response": {...},
     "timestamp": "...",
     "ttl": 3600,
     "hits": 5
   }
```

#### `test_webhook_endpoint_contract.py`
Проверяет webhook API.

```python
✅ POST /api/v1/webhooks → returns webhook_id
✅ GET /api/v1/webhooks/{id} → webhook config
✅ PUT /api/v1/webhooks/{id} → updates config
✅ DELETE /api/v1/webhooks/{id} → 204
✅ Webhook schema:
   {
     "id": "wh-123",
     "url": "https://example.com/webhook",
     "events": ["chat.response.generated", "support.handoff.required"],
     "active": true,
     "created_at": "...",
     "last_triggered_at": "..."
   }
```

---

### B. Сервис-уровень Контракты (`tests/contracts/services/`)

#### `test_search_service_contract.py`
Проверяет контракт сервиса поиска.

```python
✅ search(query) → SearchResult(docs[], scores[], metadata)
✅ Returned docs have: {id, content, metadata, similarity_score}
✅ Scores sorted in descending order
✅ Score range: [0, 1]
✅ Handles empty results gracefully
✅ SearchResult schema:
   {
     "documents": [
       {
         "id": "doc-123",
         "content": "...",
         "metadata": {
           "source": "file.pdf",
           "page": 1,
           "chunk_id": 42
         },
         "similarity_score": 0.92
       }
     ],
     "total_count": 1,
     "execution_time_ms": 123
   }
```

#### `test_cache_manager_contract.py`
Проверяет контракт кэш-менеджера.

```python
✅ get(query_hash) → CacheEntry | None
✅ set(query_hash, response, ttl) → bool
✅ delete(query_hash) → bool
✅ TTL respected (entry expired after ttl_seconds)
✅ Similarity threshold: default 0.95
✅ CacheEntry schema:
   {
     "query_hash": "abc123",
     "response": {...},
     "ttl": 3600,
     "created_at": "...",
     "expires_at": "...",
     "hits_count": 5
   }
```

#### `test_identity_manager_contract.py`
Проверяет разрешение identity.

```python
✅ resolve_identity(external_id, source) → internal_user_id
✅ Returns consistent ID for same external_id
✅ Creates new identity if not exists
✅ Validates source type (telegram, slack, email, etc)
✅ Identity schema:
   {
     "internal_id": "user-123",
     "external_id": "telegram-456",
     "source": "telegram",
     "created_at": "...",
     "last_seen": "..."
   }
```

#### `test_classification_service_contract.py`
Проверяет классификацию текста.

```python
✅ classify(text) → {intent, category, confidence}
✅ Confidence >= 0.5 for valid classification
✅ Returns default category if confidence < threshold
✅ Handles multilingual input
✅ Classification schema:
   {
     "intent": "billing",
     "category": "question",
     "confidence": 0.87,
     "alternate_intents": [
       {"intent": "account", "confidence": 0.08}
     ]
   }
```

#### `test_webhook_service_contract.py`
Проверяет сервис webhooks.

```python
✅ send_event(event_type, payload) → webhook delivery
✅ Retries on network failure (exponential backoff)
✅ Event structure: {type, timestamp, payload, user_id, session_id}
✅ Max 3 retries with delays: 1s, 2s, 4s
✅ WebhookEvent schema:
   {
     "id": "evt-123",
     "type": "chat.response.generated",
     "timestamp": "2026-01-16T10:30:00Z",
     "user_id": "user-123",
     "session_id": "sess-456",
     "payload": {...},
     "delivery_status": "delivered"
   }
```

#### `test_language_detection_contract.py`
Проверяет определение языка.

```python
✅ detect(text) → {language, confidence}
✅ Supports: en, ru, uk, be, pl, etc
✅ Confidence >= 0.3 for valid detection
✅ Returns 'unknown' if confidence too low
✅ LanguageDetection schema:
   {
     "language": "ru",
     "confidence": 0.98,
     "alternatives": [
       {"language": "uk", "confidence": 0.01}
     ]
   }
```

---

### C. Node Interface Контракты (`tests/contracts/nodes/`)

#### `test_base_node_contract.py`
Проверяет базовый интерфейс всех нодов.

```python
✅ Node.run(state) → modified_state
✅ Node respects state schema (required/optional fields)
✅ Node filters sensitive fields on output
✅ Node timeout enforced (default 30s)
✅ Node error handling: returns error state
✅ State requirements:
   {
     "question": str (required),
     "user_id": str (required),
     "session_id": str (required),
     "conversation_history": list (optional),
     "detected_language": str (optional),
     "docs": list (optional)
   }
```

#### `test_node_io_contract.py`
Проверяет I/O контракты нодов.

```python
✅ Each node validates input schema
✅ Each node validates output schema
✅ Input missing required field → ValueError
✅ Output exceeds size limits → warning log
✅ State mutations are additive, not destructive
```

---

## E2E Тесты

### A. Основные Сценарии (`tests/e2e/scenarios/`)

#### `test_simple_qa_flow.py`
**Сценарий**: Простой Q&A от пользователя

```
Шаги:
1. POST /chat with question
2. Pipeline executes:
   session_starter → input_guardrails → language_detection
   → cache_check → dialog_analysis → aggregation
   → easy_classification → query_translation
   → metadata_filtering → hybrid_search → reranking
   → generation → output_guardrails → archive_session
   → store_in_cache
3. Response returned with answer + sources
4. Session archived in DB
5. Response cached for future queries

Проверки:
✅ Status 200
✅ Response has answer, sources, processing_time
✅ Sources are relevant to question
✅ Session stored with correct metadata
✅ Processing time < 2 seconds
```

#### `test_cache_hit_flow.py`
**Сценарий**: Повторный запрос (cache hit)

```
Шаги:
1. First query → full pipeline → cached (~1.5s)
2. Identical second query
3. Cache hit detected early (skip generation)
4. Cached response returned
5. Processing time measured

Проверки:
✅ First request slower (full pipeline)
✅ Second request faster (cached, < 100ms)
✅ Both responses identical
✅ processing_time much lower on cache hit
✅ Cache similarity threshold: 0.95
```

#### `test_multi_turn_conversation.py`
**Сценарий**: Многооборотный диалог

```
Шаги:
1. User Q1 → Answer1 + session_id
2. User Q2 (references Q1) → Answer2 with context
3. Loop detection check → no infinite loops
4. Session history accumulated
5. Continue conversation for 3-5 turns

Проверки:
✅ Session_id consistent across turns
✅ Dialog analysis understands context
✅ Loop detection prevents infinite loops
✅ History properly formatted in state
✅ Each turn uses previous context
✅ Max conversation length: 10 turns per session
```

#### `test_document_ingestion_and_retrieval.py`
**Сценарий**: Загрузка документов и поиск

```
Шаги:
1. Upload PDF/DOCX via /ingestion endpoint
2. System indexes document (chunks, embeddings)
3. Query mentions topic from doc
4. Document found in hybrid search
5. Answer generated from doc content

Проверки:
✅ Document stored in PostgreSQL + Qdrant
✅ Chunks created with metadata (source, page, position)
✅ Search returns document chunks
✅ Sources attribute includes doc metadata
✅ Retrieval latency < 500ms
✅ Embedding dimension: 384
✅ Chunk overlap: 20%
```

#### `test_guardrails_workflow.py`
**Сценарий**: Защита от небезопасного контента

```
Шаги:
1. Query with toxic/PII content
2. Input guardrails block it
3. Error response returned (403 or 400)
4. Attempt output injection
5. Output guardrails filter response

Проверки:
✅ Unsafe queries blocked with error
✅ PII not logged in history
✅ Generated response filtered
✅ Security events logged
✅ Toxicity threshold: 0.7
✅ PII detection: email, phone, SSN, credit card
```

#### `test_multilingual_workflow.py`
**Сценарий**: Многоязычные запросы

```
Шаги:
1. Query in Russian
2. Language detection → "ru"
3. Query translated to doc language
4. Search on translated query
5. Response in original language

Проверки:
✅ Language detected correctly (ru, uk, en, be, pl, etc)
✅ Query translated properly
✅ Response language matches input
✅ Works for: en, ru, uk, be, pl, de, fr, es
✅ Translation quality: semantic preservation
```

#### `test_clarification_questions.py`
**Сценарий**: Уточняющие вопросы

```
Шаги:
1. Ambiguous query
2. Clarification check detects ambiguity
3. System asks clarifying questions
4. User response refines answer

Проверки:
✅ Ambiguous queries trigger clarification
✅ Suggested questions are relevant (3-5 questions)
✅ Refined answer more accurate
✅ Session state tracks clarification
✅ Confidence threshold for clarification: 0.6
```

#### `test_webhook_delivery.py`
**Сценарий**: Webhook доставка

```
Шаги:
1. Configure webhook for chat.response.generated
2. Send query → response generated
3. Webhook triggered with event payload
4. External handler receives event
5. Retry on failure

Проверки:
✅ Webhook called with correct event type
✅ Payload includes response + metadata
✅ Retry logic works (3 attempts, exponential backoff)
✅ Delivery logged in database
✅ Webhook timeout: 10s
✅ Event includes: type, timestamp, payload, user_id, session_id
```

#### `test_handoff_to_agent.py`
**Сценарий**: Передача на человека (handoff)

```
Шаги:
1. Complex query requiring human
2. State machine detects handoff condition
3. Webhook event: support.handoff.required
4. Human agent gets context

Проверки:
✅ Handoff triggered correctly
✅ Context preserved in handoff
✅ Webhook notifies external system
✅ Session marked as handoff_pending
✅ Human receives: question, context, search results, previous attempts
```

---

### B. Error & Edge Cases (`tests/e2e/error_cases/`)

#### `test_empty_document_base.py`
```
Условие: Query when no documents indexed
Ожидается: "No relevant documents found" response
Проверка: Graceful degradation, no crash
```

#### `test_database_outage.py`
```
Условие: PostgreSQL unavailable
Ожидается: Error response + graceful fallback
Проверка: No hanging requests, timeout after 5s
```

#### `test_vector_db_failure.py`
```
Условие: Qdrant unavailable
Ожидается: Fall back to lexical search only
Проверка: Search still works, quality degraded
```

#### `test_cache_corruption.py`
```
Условие: Redis returns invalid data
Ожидается: Cache bypassed, fresh computation
Проверка: No cached bad data served
```

#### `test_timeout_scenarios.py`
```
Условие: Generation timeout (LLM slow) or Search timeout (Qdrant slow)
Ожидается: Partial results + timeout error
Проверка: Timeout enforced (default 30s per node)
```

#### `test_malformed_session_state.py`
```
Условие: Session corrupted in DB
Ожидается: Create new session gracefully
Проверка: No crash, user can continue
```

#### `test_llm_api_failure.py`
```
Условие: OpenAI API unavailable
Ожидается: Error response with fallback answer
Проверка: Retry logic (3 attempts)
```

#### `test_large_document_ingestion.py`
```
Условие: Upload 100MB document
Ожидается: Proper chunking + indexing
Проверка: Memory efficient, completes in < 5 minutes
```

#### `test_rate_limiting.py`
```
Условие: Send 1000 requests in 10s
Ожидается: Rate limit enforced, 429 responses
Проверка: Rate limit: 100 req/min per user
```

---

### C. Performance & Load Tests (`tests/e2e/performance/`)

#### `test_response_latency.py`
```
Метрики:
✅ P50: < 200ms (cache hit)
✅ P95: < 500ms (cache hit)
✅ P50: < 1000ms (full pipeline)
✅ P95: < 2000ms (full pipeline)

Измерения: 100 запросов на каждый сценарий
```

#### `test_concurrent_users.py`
```
Условие: 100 concurrent queries
Ожидается: All succeed, no dropped requests

Метрики:
✅ Error rate < 0.1%
✅ P95 latency < 3s
✅ Max QPS sustained: 50
```

#### `test_pipeline_throughput.py`
```
Условие: Sustained 50 QPS for 5 minutes
Ожидается: No degradation

Мониторинг:
✅ Memory usage (baseline + delta)
✅ CPU usage
✅ DB connections (not exceeding pool)
✅ Cache hit rate (should be stable)
```

---

## Структура Тестовых Файлов

```
tests/
├── conftest.py
│  ├─ Fixtures: app_client, database, cache, mock_services
│  ├─ Markers: @pytest.mark.contract, @pytest.mark.e2e, @pytest.mark.slow
│  ├─ Setup/Teardown: DB cleanup, cache reset
│  └─ Auto-use fixtures: clean_state
│
├── contracts/
│  ├─ __init__.py
│  ├─ api/
│  │  ├─ __init__.py
│  │  ├─ test_chat_completions_contract.py
│  │  ├─ test_analysis_endpoint_contract.py
│  │  ├─ test_ingestion_endpoint_contract.py
│  │  ├─ test_cache_endpoint_contract.py
│  │  └─ test_webhook_endpoint_contract.py
│  │
│  ├─ services/
│  │  ├─ __init__.py
│  │  ├─ test_search_service_contract.py
│  │  ├─ test_cache_manager_contract.py
│  │  ├─ test_identity_manager_contract.py
│  │  ├─ test_classification_service_contract.py
│  │  ├─ test_webhook_service_contract.py
│  │  └─ test_language_detection_contract.py
│  │
│  └─ nodes/
│     ├─ __init__.py
│     ├─ test_base_node_contract.py
│     └─ test_node_io_contract.py
│
├─ e2e/
│  ├─ __init__.py
│  ├─ scenarios/
│  │  ├─ __init__.py
│  │  ├─ test_simple_qa_flow.py
│  │  ├─ test_cache_hit_flow.py
│  │  ├─ test_multi_turn_conversation.py
│  │  ├─ test_document_ingestion_and_retrieval.py
│  │  ├─ test_guardrails_workflow.py
│  │  ├─ test_multilingual_workflow.py
│  │  ├─ test_clarification_questions.py
│  │  ├─ test_webhook_delivery.py
│  │  └─ test_handoff_to_agent.py
│  │
│  ├─ error_cases/
│  │  ├─ __init__.py
│  │  ├─ test_empty_document_base.py
│  │  ├─ test_database_outage.py
│  │  ├─ test_vector_db_failure.py
│  │  ├─ test_cache_corruption.py
│  │  ├─ test_timeout_scenarios.py
│  │  ├─ test_malformed_session_state.py
│  │  ├─ test_llm_api_failure.py
│  │  ├─ test_large_document_ingestion.py
│  │  └─ test_rate_limiting.py
│  │
│  └─ performance/
│     ├─ __init__.py
│     ├─ test_response_latency.py
│     ├─ test_concurrent_users.py
│     └─ test_pipeline_throughput.py
│
└─ fixtures/
   ├─ __init__.py
   ├─ conftest.py (shared pytest fixtures)
   ├─ mock_services.py (mocked external APIs)
   ├─ sample_data.py (test documents, queries, responses)
   ├─ test_documents.py (sample PDFs, docs)
   ├─ assertions.py (custom assertions)
   └─ factories.py (factory pattern for test objects)
```

---

## Ключевые Сценарии по Компонентам

| Компонент | Contract Тест | E2E Тест | Критерий Успеха |
|-----------|---|---|---|
| **API Layer** | ✅ Request/Response Schema | ✅ Full request path | Status 200 + valid response |
| **Session Manager** | ✅ Session creation | ✅ Multi-turn flow | Consistent session_id, history |
| **Guardrails** | ✅ Input/Output contracts | ✅ Unsafe content blocking | Toxicity/PII detection working |
| **Language Detection** | ✅ Output schema | ✅ Multi-language flow | Language code + confidence |
| **Cache** | ✅ Cache interface | ✅ Cache hit/miss | Hit latency < 100ms |
| **Search (Hybrid)** | ✅ SearchResult schema | ✅ End-to-end retrieval | Relevant docs, ordered by score |
| **Reranking** | ✅ Score adjustment | ✅ Score improvement | Reranked scores > original |
| **Multi-hop** | ✅ Sub-question generation | ✅ Complex reasoning | Decomposition + synthesis |
| **Generation** | ✅ LLM response schema | ✅ Quality + relevance | Coherent answer with sources |
| **Webhooks** | ✅ Event payload | ✅ Delivery + retry | Webhook called, retries work |
| **Handoff** | ✅ Handoff event | ✅ Human escalation | Context passed correctly |

---

## Команды Запуска

### Запуск всех тестов
```bash
pytest tests/ -v
```

### Только контрактные тесты (быстро)
```bash
pytest tests/contracts/ -v -m contract
```

### Только E2E сценарии
```bash
pytest tests/e2e/scenarios/ -v -m e2e
```

### E2E (исключить performance)
```bash
pytest tests/e2e/scenarios tests/e2e/error_cases -v -m "not slow"
```

### Только performance тесты
```bash
pytest tests/e2e/performance/ -v -m slow
```

### Contract + E2E (исключи slow)
```bash
pytest tests/contracts tests/e2e -v -m "not slow"
```

### С покрытием кода
```bash
pytest tests/ --cov=app --cov-report=html
```

### Параллельно (12 воркеров)
```bash
pytest tests/ -n 12 -v
```

### Только failed тесты (после предыдущего run)
```bash
pytest tests/ --lf -v
```

### Конкретный файл теста
```bash
pytest tests/e2e/scenarios/test_simple_qa_flow.py -v
```

### Конкретный тест
```bash
pytest tests/e2e/scenarios/test_simple_qa_flow.py::test_chat_flow -v
```

### С выводом логов
```bash
pytest tests/ -v -s --log-cli-level=INFO
```

### Пример CI/CD workflow
```bash
# 1. Запустить contract тесты (быстро)
pytest tests/contracts/ -v

# 2. Запустить e2e + error cases
pytest tests/e2e/scenarios tests/e2e/error_cases -v

# 3. Запустить performance (опционально)
pytest tests/e2e/performance/ -v --timeout=600

# 4. Генерировать отчет
pytest tests/ --cov=app --cov-report=html --junit-xml=test-results.xml
```

---

## Fixtures & Test Data

### conftest.py - Основные Fixtures

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

@pytest.fixture
async def app_client():
    """FastAPI test client with test database"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
async def database():
    """Test database with cleanup"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def clean_cache():
    """Clear Redis cache before test"""
    redis_client = aioredis.from_url("redis://localhost")
    await redis_client.flushdb()
    yield redis_client
    await redis_client.close()

@pytest.fixture
def mock_llm():
    """Mock OpenAI API responses"""
    with patch("openai.ChatCompletion.create") as mock:
        mock.return_value = {
            "choices": [{"message": {"content": "Mocked response"}}]
        }
        yield mock

@pytest.fixture
def sample_documents():
    """Pre-indexed documents for retrieval tests"""
    return [
        {
            "id": "doc-1",
            "content": "How to reset password...",
            "metadata": {"source": "kb.pdf", "page": 1}
        },
        {
            "id": "doc-2",
            "content": "Billing and pricing information...",
            "metadata": {"source": "billing.pdf", "page": 2}
        }
    ]

@pytest.fixture
async def session_context():
    """Pre-configured session with history"""
    return {
        "session_id": "sess-test-123",
        "user_id": "user-123",
        "conversation_history": [
            {"role": "user", "content": "What is the pricing?"},
            {"role": "assistant", "content": "We have two plans..."}
        ]
    }

@pytest.fixture
def mock_webhook_server():
    """Mock webhook endpoint that catches events"""
    events = []

    @app.post("/webhook")
    async def webhook_handler(request):
        events.append(await request.json())
        return {"status": "received"}

    yield events
```

### Markers для Тестов

```python
# pytest.ini
[pytest]
markers =
    contract: Contract tests between components
    e2e: End-to-end user flow tests
    slow: Slow performance tests (use -m "not slow" to skip)
    integration: Integration tests
    unit: Unit tests
```

---

## Метрики Успеха

### Code Coverage
- **Minimum**: `> 80%` основного кода пайплайна
- **Target**: `> 90%` критических компонентов
- **Measured**: `pytest --cov=app`

### Test Pass Rate
- **Contract Tests**: `100%` pass rate (required for merge)
- **E2E Tests**: `100%` pass rate (required for merge)
- **Performance Tests**: No degradation vs baseline

### Performance Baselines
| Метрика | Target | P95 |
|---------|--------|-----|
| Cache hit latency | < 100ms | < 200ms |
| Full pipeline | < 1500ms | < 2500ms |
| Search only | < 500ms | < 800ms |
| Generation only | < 1000ms | < 1500ms |

### Reliability
- **Error Rate**: `< 0.1%` при нормальной нагрузке
- **Timeout Rate**: `0%` (timeouts treated as failures)
- **Flaky Tests**: `0` (deterministic tests only)

### Execution Time
- **Contract Tests**: `< 2 minutes`
- **E2E Scenarios**: `< 5 minutes`
- **Error Cases**: `< 3 minutes`
- **Performance Tests**: `< 10 minutes`
- **Total Suite**: `< 20 minutes` (or `< 5 min` with `-m "not slow"`)

### Test Coverage by Component

| Компонент | Unit | Integration | E2E | Needed? |
|-----------|------|-----------|-----|---------|
| API Endpoints | ❌ | ✅ Contract | ✅ E2E | All |
| Session Manager | ❌ | ✅ Contract | ✅ E2E | All |
| Guardrails | ❌ | ✅ Contract | ✅ E2E | All |
| Search Service | ❌ | ✅ Contract | ✅ E2E | All |
| Cache Manager | ❌ | ✅ Contract | ✅ E2E | All |
| Language Detection | ✅ Existing | ✅ Contract | ✅ E2E | All |
| Classification | ✅ Existing | ✅ Contract | ✅ E2E | All |
| Generation | ❌ | ✅ Contract | ✅ E2E | All |
| Webhooks | ❌ | ✅ Contract | ✅ E2E | All |
| Dialog Analysis | ✅ Existing | ✅ Contract | ✅ E2E | All |

---

## Дополнительные Материалы

### Related Documentation
- [CODE_IMPROVEMENTS_PLAN.md](./CODE_IMPROVEMENTS_PLAN.md) - Рекомендации по улучшению проекта
- [PROJECT_QUALITY_REVIEW.md](./PROJECT_QUALITY_REVIEW.md) - Подробный анализ качества
- [PERFORMANCE_FIX_PLAN.md](./PERFORMANCE_FIX_PLAN.md) - План оптимизации производительности

### Test Data Requirements
- Sample documents (PDF, DOCX, TXT)
- Sample queries with expected answers
- Mock external API responses
- Test user profiles
- Test webhook endpoints

### CI/CD Integration
- GitHub Actions workflow for automated test runs
- Slack notifications on test failures
- Coverage badges in README
- Performance regression detection

---

## Roadmap Реализации

### Phase 1: Foundation (Week 1)
- [ ] Setup pytest infrastructure
- [ ] Create conftest.py and fixtures
- [ ] Implement basic contract tests (API endpoints)

### Phase 2: Core Tests (Week 2-3)
- [ ] Contract tests for all services
- [ ] E2E scenario tests
- [ ] Error case tests

### Phase 3: Advanced Tests (Week 4)
- [ ] Performance tests
- [ ] Load tests
- [ ] Integration with CI/CD

### Phase 4: Maintenance (Ongoing)
- [ ] Fix flaky tests
- [ ] Add tests for new features
- [ ] Update baselines as code evolves

---

**Создано**: 2026-01-16
**Статус**: Ready for Implementation
**Версия плана**: 1.0

