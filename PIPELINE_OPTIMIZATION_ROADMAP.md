# 🚀 Pipeline Optimization Roadmap

> **Документ создан:** 2026-01-05  
> **Версия:** 1.0  
> **Статус:** В работе  
> **Общее время pipeline (текущее):** ~12 секунд  
> **Целевое время:** < 2 секунд

---

## 📊 Исходные данные (Trace Analysis)

| Метрика | Текущее значение | Целевое значение |
|---------|-----------------|------------------|
| Общее время запроса | 12.1 сек | < 2 сек |
| `hybrid_search` | 8.1 сек (67%) | < 500 мс |
| `generation` (LLM) | 3.2 сек | 2-3 сек (норма) |
| Rerank best score | 0.0024 | > 0.5 |
| Classification confidence | 0.55 | > 0.8 |
| Cache hit rate | 0% | > 40% |

---

## 🎯 Фаза 1: Критические исправления производительности

**Цель:** Снизить время ответа с 12 до 3-4 секунд  
**Срок:** 2-3 дня  
**Приоритет:** 🔴 Критический

---

### Задача 1.1: Оптимизация Qdrant Client (Singleton + Async)

**Проблема:**  
Vector search занимает 8 секунд. Клиент Qdrant создаётся на каждый запрос, отсутствует connection pooling.

**Решение:**  
По документации Qdrant: использовать `AsyncQdrantClient` как singleton с настроенным `pool_size`.

**Изменения:**
```python
# app/integrations/qdrant/qdrant_client.py

from qdrant_client import AsyncQdrantClient
from functools import lru_cache

_client: AsyncQdrantClient | None = None

async def get_qdrant_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            url=settings.qdrant_url,
            prefer_grpc=True,  # gRPC быстрее REST
            grpc_options={
                "grpc.max_receive_message_length": 50 * 1024 * 1024,
            }
        )
    return _client
```

**Файлы для изменения:**
- `app/integrations/qdrant/qdrant_client.py`
- `app/nodes/hybrid_search/node.py`
- `app/nodes/retrieval/node.py`

**Критерии приёмки:**
- [ ] Qdrant client создаётся один раз при старте приложения
- [ ] Используется gRPC вместо REST API
- [ ] Connection reuse подтверждён в логах
- [ ] Vector search время < 200ms (проверить в trace)

---

### Задача 1.2: Параллельный поиск (Vector + Lexical)

**Проблема:**  
Vector search и Lexical search выполняются **последовательно**, хотя независимы друг от друга.

**Решение:**  
Использовать `asyncio.gather()` для параллельного выполнения.

**Изменения:**
```python
# app/nodes/hybrid_search/node.py

async def execute(self, state: PipelineState) -> dict:
    query = state.get("aggregated_query") or state["question"]
    
    # Параллельный запуск
    vector_task = self._vector_search(query, state.get("matched_category"))
    lexical_task = self._lexical_search(query)
    
    vector_results, lexical_results = await asyncio.gather(
        vector_task,
        lexical_task,
        return_exceptions=True
    )
    
    # Fusion результатов
    return self._fuse_results(vector_results, lexical_results)
```

**Критерии приёмки:**
- [ ] Vector и Lexical search запускаются одновременно
- [ ] Общее время hybrid_search = max(vector, lexical) а не sum
- [ ] Hybrid search время < 500ms
- [ ] Graceful degradation при ошибке одного из поисков

---

### Задача 1.3: PostgreSQL Full-Text Search Optimization

**Проблема:**  
Lexical search занимает 8 секунд. Отсутствует GIN индекс на `tsvector`.

**Решение:**  
По документации PostgreSQL: добавить stored `tsvector` column с GIN индексом.

**SQL миграция:**
```sql
-- migrations/007_add_tsvector_index.sql

-- 1. Добавить stored tsvector column
ALTER TABLE qa_documents 
ADD COLUMN search_vector tsvector 
GENERATED ALWAYS AS (
    setweight(to_tsvector('russian', coalesce(question, '')), 'A') ||
    setweight(to_tsvector('russian', coalesce(answer, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(question, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(answer, '')), 'B')
) STORED;

-- 2. Создать GIN индекс
CREATE INDEX idx_qa_search_vector ON qa_documents USING GIN(search_vector);

-- 3. Создать индекс на category для фильтрации
CREATE INDEX idx_qa_category ON qa_documents((metadata->>'category'));

-- 4. Analyze для оптимизации query planner
ANALYZE qa_documents;
```

**Файлы для изменения:**
- `app/db/migrations/007_add_tsvector_index.sql` (новый)
- `app/nodes/lexical_search/lexical_search_db.py`

**Критерии приёмки:**
- [ ] GIN индекс создан и используется (проверить через EXPLAIN ANALYZE)
- [ ] Lexical search время < 50ms
- [ ] Поддержка русского и английского языков
- [ ] Работает фильтрация по category

---

### Задача 1.4: PostgreSQL Connection Pooling

**Проблема:**  
Каждый запрос может создавать новое подключение к PostgreSQL.

**Решение:**  
Использовать `asyncpg` pool с правильной конфигурацией.

**Изменения:**
```python
# app/db/connection.py

import asyncpg
from contextlib import asynccontextmanager

_pool: asyncpg.Pool | None = None

async def init_db_pool():
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=5,
        max_size=20,
        command_timeout=5.0,  # 5 секунд таймаут
        statement_cache_size=100,  # Кэширование prepared statements
    )

@asynccontextmanager
async def get_connection():
    async with _pool.acquire() as conn:
        yield conn
```

**Файлы для изменения:**
- `app/db/connection.py`
- `app/main.py` (lifespan)
- `app/nodes/lexical_search/lexical_search_db.py`

**Критерии приёмки:**
- [ ] Connection pool создаётся при старте приложения
- [ ] Pool size: min=5, max=20
- [ ] Statement caching включён
- [ ] Нет "connection refused" ошибок под нагрузкой

---

## 🎯 Фаза 2: Исправление качества ML-моделей

**Цель:** Повысить качество классификации и reranking  
**Срок:** 3-4 дня  
**Приоритет:** 🟠 Высокий

---

### Задача 2.1: Исправление формата входных данных для BGE Reranker

**Проблема:**  
Rerank scores критически низкие (0.0024). Модель `BAAI/bge-reranker-v2-m3` получает документы в формате "Question: ... Answer: ...", а должна получать чистый текст.

**Документация BGE:**
- Ожидает пары `(query, passage)` где passage — plain text
- Максимум 512 токенов на пару
- Возвращает relevance score → sigmoid → [0, 1]

**Решение:**
```python
# app/nodes/reranking/ranker.py

def _prepare_pairs(self, query: str, docs: list[str]) -> list[tuple[str, str]]:
    """Подготовить пары для reranker в правильном формате."""
    pairs = []
    for doc in docs:
        # Извлекаем только ответ, убираем Question/Answer форматирование
        clean_doc = self._extract_answer(doc)
        pairs.append((query, clean_doc))
    return pairs

def _extract_answer(self, doc: str) -> str:
    """Извлечь только ответ из документа."""
    if "Answer:" in doc:
        return doc.split("Answer:", 1)[1].strip()
    return doc

async def rerank(self, query: str, docs: list[str]) -> list[tuple[str, float]]:
    pairs = self._prepare_pairs(query, docs)
    
    # Batch inference для скорости
    inputs = self.tokenizer(
        pairs,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt"
    )
    
    with torch.no_grad():
        scores = self.model(**inputs).logits.squeeze(-1)
        scores = torch.sigmoid(scores).tolist()
    
    return sorted(zip(docs, scores), key=lambda x: -x[1])
```

**Файлы для изменения:**
- `app/nodes/reranking/ranker.py`
- `app/services/reranker/reranker.py`

**Критерии приёмки:**
- [ ] Rerank scores > 0.5 для релевантных документов
- [ ] Input format: `(query, clean_answer)` без "Question:" prefix
- [ ] Batch processing работает
- [ ] Токенизация ограничена 512 токенами

---

### Задача 2.2: Добавить "query:" prefix для E5 embeddings

**Проблема:**  
Модель `intfloat/multilingual-e5-small` требует prefix "query: " для запросов, иначе качество embeddings страдает.

**Документация E5:**
> For classification/clustering/semantic similarity, prepend "query: " to input texts.

**Решение:**
```python
# app/integrations/embeddings/get_embedding.py

def get_embedding(text: str, is_query: bool = True) -> list[float]:
    """
    Получить embedding для текста.
    
    Args:
        text: Входной текст
        is_query: True для запросов пользователя, False для документов
    """
    if is_query:
        text = f"query: {text}"
    else:
        text = f"passage: {text}"
    
    return model.encode(text, normalize_embeddings=True).tolist()
```

**Файлы для изменения:**
- `app/integrations/embeddings/get_embedding.py`
- `app/nodes/hybrid_search/node.py`
- `app/nodes/retrieval/node.py`
- `scripts/index_documents.py` (для переиндексации)

**Критерии приёмки:**
- [ ] Запросы пользователей имеют prefix "query: "
- [ ] Документы в Qdrant проиндексированы с prefix "passage: "
- [ ] Vector search precision улучшился (A/B тест)
- [ ] Embeddings нормализованы

---

### Задача 2.3: Улучшение Dialog Analysis (определение is_question)

**Проблема:**  
`is_question: false` для явного вопроса "tell about your shipping opportunities".

**Решение:**  
Добавить ML-based question detection или расширить rule-based логику.

**Изменения:**
```python
# app/nodes/dialog_analysis/rules/question_detector.py

QUESTION_PATTERNS = [
    r'\?$',                          # Заканчивается на ?
    r'^(what|how|why|when|where|who|which|can|do|does|is|are|will|would|could)\b',
    r'^(как|почему|когда|где|кто|какой|можно|ли)\b',
    r'\b(tell me|explain|describe|show|help)\b',
    r'\b(расскажи|объясни|покажи|помоги)\b',
    r'\b(about|про|о|об)\b.*\??\s*$',  # Вопрос о чём-то
]

def is_question(text: str) -> bool:
    text_lower = text.lower().strip()
    
    for pattern in QUESTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    return False
```

**Файлы для изменения:**
- `app/nodes/dialog_analysis/rules/question_detector.py` (новый)
- `app/nodes/dialog_analysis/node.py`
- `app/nodes/dialog_analysis/config.yaml`

**Критерии приёмки:**
- [ ] "Tell me about X" определяется как вопрос
- [ ] "Pls tell about X" определяется как вопрос
- [ ] Вопросы с "?" определяются корректно
- [ ] Поддержка русского и английского языков
- [ ] Unit tests покрывают edge cases

---

## 🎯 Фаза 3: Оптимизация State Management

**Цель:** Уменьшить размер state и избежать дублирования  
**Срок:** 2-3 дня  
**Приоритет:** 🟡 Средний

---

### Задача 3.1: Reducers для State

**Проблема:**  
State содержит дублированные данные:
- `docs` возвращаются из 3 nodes
- `matched_category` и `semantic_category` — одно и то же
- Вся история передаётся на каждом шаге

**Решение:**  
Использовать LangGraph reducers для оптимизации.

**Изменения:**
```python
# app/pipeline/state.py

from typing import Annotated
from langgraph.graph import add_messages

def keep_latest(existing: list | None, new: list | None) -> list:
    """Reducer: сохранять только последнюю версию."""
    return new if new is not None else existing

def merge_unique(existing: list | None, new: list | None) -> list:
    """Reducer: объединять уникальные элементы."""
    if existing is None:
        return new or []
    if new is None:
        return existing
    seen = set()
    result = []
    for item in existing + new:
        key = item if isinstance(item, str) else str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result

class PipelineState(TypedDict):
    question: str
    user_id: str
    session_id: str
    
    # Используем reducers
    docs: Annotated[list[str], keep_latest]
    conversation_history: Annotated[list[dict], add_messages]
    
    # Унифицируем категории
    category: str  # Вместо matched_category + semantic_category
    
    # Confidence теперь один
    confidence: float  # Вместо множества разных confidence
```

**Файлы для изменения:**
- `app/pipeline/state.py`
- Все nodes которые обновляют state

**Критерии приёмки:**
- [ ] State size уменьшился на 40%+
- [ ] Нет дублирования docs между nodes
- [ ] Единый формат для category/intent
- [ ] Reducers корректно обрабатывают None

---

### Задача 3.2: Lazy Loading для User Profile и Session History

**Проблема:**  
User profile и session history загружаются всегда, даже когда не нужны.

**Решение:**  
Загружать только при необходимости (для prompt_routing и generation).

**Изменения:**
```python
# app/nodes/session_starter/node.py

async def execute(self, state: PipelineState) -> dict:
    result = {}
    
    # Загружаем user_profile только если нужен
    if self.params.get("load_user_profile", True):
        result["user_profile"] = await self._load_user_profile(state["user_id"])
    
    # Session history загружаем lazy
    result["_session_history_loader"] = lambda: self._load_session_history(
        state["session_id"]
    )
    
    return result
```

**Критерии приёмки:**
- [ ] Session history загружается только в prompt_routing
- [ ] User profile загружается только когда нужен
- [ ] Общее время session_starter < 30ms

---

### Задача 3.3: Trimming Conversation History

**Проблема:**  
В conversation_history передаётся вся история (4+ сообщений), что увеличивает tokens и стоимость.

**Решение:**  
Использовать `trim_messages` и summarization.

**Изменения:**
```python
# app/nodes/prompt_routing/node.py

from langchain_core.messages import trim_messages

def _prepare_history(self, history: list[dict], max_tokens: int = 500) -> str:
    """Подготовить историю с trimming."""
    
    # Конвертируем в LangChain messages
    messages = [
        HumanMessage(content=m["content"]) if m["role"] == "user"
        else AIMessage(content=m["content"])
        for m in history
    ]
    
    # Trim до max_tokens
    trimmed = trim_messages(
        messages,
        max_tokens=max_tokens,
        strategy="last",  # Оставляем последние
        token_counter=self._count_tokens,
        include_system=False
    )
    
    return self._format_messages(trimmed)
```

**Критерии приёмки:**
- [ ] Conversation history ограничена 500 токенами
- [ ] Используется strategy="last" для сохранения контекста
- [ ] Summarization для старых сообщений (опционально)

---

## 🎯 Фаза 4: Language Detection и Localization

**Цель:** Отвечать на языке пользователя  
**Срок:** 1-2 дня  
**Приоритет:** 🟡 Средний

---

### Задача 4.1: Language Detection Node

**Проблема:**  
Пользователь пишет на английском, система отвечает на русском.

**Решение:**  
Добавить language detection и передавать язык в generation.

**Изменения:**
```python
# app/nodes/language_detection/node.py

from langdetect import detect, detect_langs

class LanguageDetectionNode(BaseNode):
    """Определяет язык запроса пользователя."""
    
    async def execute(self, state: PipelineState) -> dict:
        question = state["question"]
        
        try:
            detected = detect_langs(question)
            primary_lang = detected[0]
            
            return {
                "detected_language": primary_lang.lang,
                "language_confidence": round(primary_lang.prob, 2)
            }
        except:
            return {
                "detected_language": "ru",  # fallback
                "language_confidence": 0.5
            }
```

**Изменения в generation:**
```python
# app/nodes/generation/node.py

def _build_system_prompt(self, state: PipelineState) -> str:
    lang = state.get("detected_language", "ru")
    
    if lang == "en":
        return "You are a helpful support assistant. Answer clearly and concisely."
    else:
        return "Ты - эмпатичный ассистент поддержки. Отвечай четко и кратко."
```

**Файлы:**
- `app/nodes/language_detection/` (новый node)
- `app/nodes/generation/node.py`
- `app/pipeline/graph.py`
- `app/pipeline/pipeline_order.yaml`

**Критерии приёмки:**
- [ ] Английские запросы → английские ответы
- [ ] Русские запросы → русские ответы
- [ ] Language detection < 5ms
- [ ] Fallback на русский при неопределённом языке

---

## 🎯 Фаза 5: Caching и Warm-up

**Цель:** Увеличить cache hit rate до 40%+  
**Срок:** 2 дня  
**Приоритет:** 🟢 Нормальный

---

### Задача 5.1: Semantic Cache

**Проблема:**  
Текущий cache key: `"hi opportunities pls shipping tell your"` — простая нормализация. Похожие вопросы не попадают в cache.

**Решение:**  
Использовать semantic similarity для cache lookup.

**Изменения:**
```python
# app/nodes/check_cache/semantic_cache.py

class SemanticCache:
    def __init__(self, similarity_threshold: float = 0.92):
        self.threshold = similarity_threshold
        self.embedding_model = get_embedding_model()
    
    async def get(self, query: str) -> dict | None:
        query_embedding = self.embedding_model.encode(f"query: {query}")
        
        # Поиск в Redis с использованием vector similarity
        cached_items = await self._get_recent_cache_items(limit=100)
        
        for item in cached_items:
            similarity = cosine_similarity(query_embedding, item["embedding"])
            if similarity >= self.threshold:
                return item["response"]
        
        return None
    
    async def set(self, query: str, response: dict, ttl: int = 86400):
        embedding = self.embedding_model.encode(f"query: {query}")
        await redis.set(
            f"cache:{hash(query)}",
            {
                "query": query,
                "embedding": embedding.tolist(),
                "response": response,
            },
            ex=ttl
        )
```

**Критерии приёмки:**
- [ ] Semantic similarity threshold = 0.92
- [ ] Cache hit для парафразов ("How can I track package?" ≈ "Track my order")
- [ ] Cache hit rate > 40% на production traffic
- [ ] TTL = 24 часа

---

### Задача 5.2: Model Warm-up при старте

**Проблема:**  
Первый запрос медленный из-за lazy loading моделей.

**Решение:**  
Warm-up всех моделей в lifespan.

**Изменения:**
```python
# app/main.py

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🔥 Warming up models...")
    
    # Parallel warmup
    await asyncio.gather(
        warm_up_embedding_model(),
        warm_up_reranker_model(),
        warm_up_classification_model(),
        init_qdrant_client(),
        init_db_pool(),
    )
    
    logger.info("✅ All models warmed up")
    yield
    
    # Cleanup
    await close_qdrant_client()
    await close_db_pool()
```

**Критерии приёмки:**
- [ ] Все модели загружены при старте
- [ ] Первый запрос не медленнее последующих
- [ ] Startup time < 30 секунд
- [ ] Graceful shutdown

---

## 🎯 Фаза 6: Мониторинг и Observability

**Цель:** Отслеживать производительность в production  
**Срок:** 1-2 дня  
**Приоритет:** 🟢 Нормальный

---

### Задача 6.1: Добавить метрики в каждый node

**Решение:**
```python
# app/nodes/base_node/node.py

import time
from prometheus_client import Histogram, Counter

NODE_LATENCY = Histogram(
    'pipeline_node_latency_seconds',
    'Node execution latency',
    ['node_name']
)

NODE_ERRORS = Counter(
    'pipeline_node_errors_total',
    'Node error count',
    ['node_name', 'error_type']
)

class BaseNode:
    async def __call__(self, state: PipelineState) -> dict:
        start = time.perf_counter()
        try:
            result = await self.execute(state)
            NODE_LATENCY.labels(node_name=self.name).observe(
                time.perf_counter() - start
            )
            return result
        except Exception as e:
            NODE_ERRORS.labels(
                node_name=self.name,
                error_type=type(e).__name__
            ).inc()
            raise
```

**Метрики для дашборда:**
- `pipeline_total_latency_p95` — общее время ответа
- `pipeline_node_latency_p95` по каждому node
- `rerank_best_score` — качество reranking
- `classification_confidence` — уверенность классификации
- `cache_hit_rate` — процент cache hits
- `error_rate` — процент ошибок

**Критерии приёмки:**
- [ ] Prometheus метрики для всех nodes
- [ ] Grafana дашборд с ключевыми метриками
- [ ] Alerts для P95 latency > 5 сек
- [ ] Alerts для error rate > 1%

---

## 📋 Чеклист внедрения

### Фаза 1 (Критические исправления)
- [ ] 1.1 Qdrant singleton client
- [ ] 1.2 Параллельный hybrid search
- [ ] 1.3 PostgreSQL GIN index
- [ ] 1.4 PostgreSQL connection pool
- [ ] **Checkpoint:** Время ответа < 4 сек

### Фаза 2 (ML Quality)
- [ ] 2.1 BGE Reranker input format
- [ ] 2.2 E5 "query:" prefix
- [ ] 2.3 Question detection
- [ ] **Checkpoint:** Rerank score > 0.5, Classification > 0.8

### Фаза 3 (State Management)
- [ ] 3.1 State reducers
- [ ] 3.2 Lazy loading
- [ ] 3.3 History trimming
- [ ] **Checkpoint:** State size -40%

### Фаза 4 (Localization)
- [ ] 4.1 Language detection
- [ ] **Checkpoint:** Correct language in 95% responses

### Фаза 5 (Caching)
- [ ] 5.1 Semantic cache
- [ ] 5.2 Model warm-up
- [ ] **Checkpoint:** Cache hit rate > 40%

### Фаза 6 (Monitoring)
- [ ] 6.1 Node metrics
- [ ] **Checkpoint:** Dashboards operational

---

## 📊 Ожидаемые результаты

| Метрика | До | После Фазы 1 | После всех фаз |
|---------|-----|-------------|----------------|
| Общее время | 12.1s | < 4s | < 2s |
| Hybrid search | 8.1s | < 500ms | < 300ms |
| Rerank score | 0.002 | > 0.3 | > 0.5 |
| Classification | 0.55 | 0.75 | > 0.8 |
| Cache hits | 0% | 20% | > 40% |
| Correct language | 0% | 50% | 95% |

---

## 🔗 Ссылки на документацию

- [Qdrant AsyncQdrantClient](https://qdrant.tech/documentation/sdk/python-async/)
- [Qdrant Performance Tuning](https://qdrant.tech/documentation/guides/optimization/)
- [PostgreSQL GIN Indexes](https://www.postgresql.org/docs/current/textsearch-indexes.html)
- [BGE Reranker v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [E5 Multilingual Small](https://huggingface.co/intfloat/multilingual-e5-small)
- [LangGraph State Management](https://langchain-ai.github.io/langgraph/concepts/low_level/)
