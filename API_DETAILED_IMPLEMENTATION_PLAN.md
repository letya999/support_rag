# Полный детальный план реструктуризации API Support RAG

**Статус:** Детальный план с указанием всех файлов, изменений и эндпоинтов
**Дата:** 2025-01-09
**Версия API:** v1
**Всего эндпоинтов:** 45+

---

## 📋 Оглавление

1. [Архитектурные основы](#архитектурные-основы)
2. [Файлы для создания/модификации](#файлы-для-созданиямодификации)
3. [Фаза 1: Инфраструктура и Middleware](#фаза-1-инфраструктура-и-middleware)
4. [Фаза 2: Миграция существующих эндпоинтов](#фаза-2-миграция-существующих-эндпоинтов)
5. [Фаза 3: Chat & Generation - 6 эндпоинтов](#фаза-3-chat--generation---6-эндпоинтов)
6. [Фаза 4: Knowledge Base - 7 эндпоинтов](#фаза-4-knowledge-base---7-эндпоинтов)
7. [Фаза 5: Intelligence - 4 эндпоинта](#фаза-5-intelligence---4-эндпоинта)
8. [Фаза 6: Taxonomy - 8 эндпоинтов](#фаза-6-taxonomy---8-эндпоинтов)
9. [Фаза 7: History - 6 эндпоинтов](#фаза-7-history---6-эндпоинтов)
10. [Фаза 8: Cache Debugging - 6 эндпоинтов](#фаза-8-cache-debugging---6-эндпоинтов)
11. [Фаза 9: System - 6 эндпоинтов](#фаза-9-system---6-эндпоинтов)
12. [Фаза 10: Channels Integration - 6 эндпоинтов](#фаза-10-channels-integration---6-эндпоинтов)
13. [Финальные шаги](#финальные-шаги)
14. [Чек-лист реализации](#чек-лист-реализации)

---

## Архитектурные основы

### Принципы проектирования

**1. Версионирование:** Все эндпойнты используют префикс `/api/v1/`

**2. Envelope Pattern:** Единый формат всех ответов:

```json
{
  "success": true/false,
  "data": {...},
  "error": "Optional error message",
  "request_id": "Unique request identifier",
  "timestamp": "2025-01-09T12:00:00Z",
  "metadata": {...}
}
```

**3. Обработка ошибок:** Стандартные HTTP коды + custom error codes

**4. Сеть и безопасность:**
- ✅ **Текущее:** Система работает в закрытой корпоративной сети
- ✅ **Аутентификация НЕ требуется** на текущий момент
- ℹ️ **Headers для трассировки:**
  - `X-Request-ID: <id>` (генерируется автоматически, опционально передать свой)
  - `X-User-ID: <user_id>` (опционально для логирования метаданных запроса)
- 🔮 **Зарезервировано для будущего:** Поддержка Bearer tokens при необходимости расширения на внешние сети

**5. Rate Limiting:** Разные лимиты для разных групп эндпоинтов (для защиты от перегрузок)

---

## Файлы для создания/модификации

### Создать (новые файлы)
```
app/api/middleware.py              # RequestID, Security Headers middleware
app/api/rate_limiting.py           # Limiter configuration
app/api/chat_routes.py             # Chat & Generation endpoints
app/api/knowledge_base_routes.py   # Knowledge Base endpoints
app/api/intelligence_routes.py     # Intelligence endpoints
app/api/taxonomy_routes.py         # Taxonomy endpoints
app/api/history_routes.py          # History endpoints
app/api/cache_routes.py            # Cache debugging endpoints
app/api/system_routes.py           # System endpoints
app/api/channels_routes.py         # Channels integration endpoints
API_DETAILED_IMPLEMENTATION_PLAN.md # This file
API_EXAMPLES.md                    # API usage examples
tests/test_api_endpoints.py        # API endpoint tests
```

### Обновить (существующие файлы)
```
app/main.py                        # Add middleware and route includes
app/api/main.py                    # Update route prefixes to /api/v1/
app/api/schemas.py                 # Add APIResponse and error schemas
app/api/exceptions.py              # Add custom exception classes
app/api/rag_routes.py              # Update to new response format
app/api/admin_routes.py            # Update to new response format
app/api/config_routes.py           # Update to new response format
app/api/document_routes.py         # Update to new response format
app/api/metadata_routes.py         # Update to new response format
README.md                          # Update with new API info
```

---

## Фаза 1: Инфраструктура и Middleware

### 1.1 Создать `app/api/middleware.py`

**Назначение:** Request ID генерация, Security headers

**Компоненты:**
- `RequestIDMiddleware` - генерирует/пропагирует X-Request-ID
- `SecurityHeadersMiddleware` - добавляет security headers

**Функции:**
```
- Логирование каждого запроса с ID
- Добавление X-Content-Type-Options: nosniff
- Добавление X-Frame-Options: DENY
- Добавление X-XSS-Protection
- Добавление HSTS header
```

### 1.2 Создать `app/api/rate_limiting.py`

**Назначение:** Ограничение частоты запросов

**Rate Limits по эндпоинтам:**
```
- /chat/sync, /chat/async, /chat/escalate: 20/minute
- /kb/upload: 10/minute
- /kb/search: 30/minute
- /intelligence/*: 15/minute
- /system/*: 100/minute
- /cache/*: 50/minute (только для admin)
- Default: 100/minute
```

**Обработчик:** `rate_limit_exceeded_handler` возвращает 429 с Retry-After

### 1.3 Обновить `app/api/schemas.py`

**Добавить:**
```python
# APIResponse с Generic типом
class APIResponse[T](BaseModel):
    success: bool
    data: Optional[T]
    error: Optional[str]
    request_id: str
    timestamp: datetime
    metadata: Optional[dict]

# Error schemas
class ValidationErrorResponse(BaseModel)
class NotFoundErrorResponse(BaseModel)
class ConflictErrorResponse(BaseModel)
```

### 1.4 Обновить `app/api/exceptions.py`

**Добавить классы:**
- `APIException` - базовый класс
- `ValidationError` - 400 Bad Request
- `NotFoundError` - 404 Not Found
- `UnauthorizedError` - 401 Unauthorized
- `ForbiddenError` - 403 Forbidden
- `ConflictError` - 409 Conflict

**Добавить handler:**
```python
async def api_exception_handler(request, exc)
```

### 1.5 Обновить `app/main.py`

**Добавить:**
```python
from app.api.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.api.rate_limiting import limiter
from app.api.exceptions import APIException, api_exception_handler

# Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)

# Exception handlers
app.add_exception_handler(APIException, api_exception_handler)

# Include all API routes
app.include_router(api_main.router)
```

---

## Фаза 2: Миграция существующих эндпоинтов

### 2.1 Обновить `app/api/main.py`

**Изменения:**
- Префикс всех маршрутов на `/api/v1`
- Добавить rate limiting зависимости
- Организовать маршруты по группам с тегами

**Новая структура:**
```python
router = APIRouter(prefix="/api/v1")

# RAG routes
router.include_router(rag_routes.router, tags=["Chat & Generation"])

# Knowledge Base routes
router.include_router(document_routes.router, prefix="/kb", tags=["Knowledge Base"])

# Config routes
router.include_router(config_routes.router, prefix="/config", tags=["Config"])

# System routes
router.include_router(admin_routes.router, prefix="/admin", tags=["System"])
```

### 2.2 Обновить все существующие эндпойнты

**Для каждого файла (rag_routes, admin_routes, etc):**

**Было:**
```python
@router.get("/health")
async def health():
    return {"status": "healthy"}
```

**Стало:**
```python
@router.get("/health")
async def health(request: Request) -> APIResponse[dict]:
    return APIResponse(
        success=True,
        data={"status": "healthy"},
        request_id=request.state.request_id,
        timestamp=datetime.utcnow()
    )
```

---

## Фаза 3: Chat & Generation - 6 эндпоинтов

### Путь: `/api/v1/chat`

#### 3.1 POST `/api/v1/chat/sync`
**Назначение:** Синхронный диалог с ассистентом

**Request:**
```json
{
  "message": "string",
  "session_id": "string",
  "user_id": "string",
  "conversation_history": [
    {"role": "user", "content": "string", "timestamp": "2025-01-09T..."}
  ],
  "stream": false,
  "metadata": {}
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "message": "string",
    "sources": [{"title": "...", "url": "..."}],
    "confidence": 0.95,
    "conversation_id": "string",
    "metadata": {}
  },
  "request_id": "uuid",
  "timestamp": "2025-01-09T..."
}
```

**Rate Limit:** 20/minute

#### 3.2 POST `/api/v1/chat/async`
**Назначение:** Асинхронная генерация (для длительных операций)

**Request:**
```json
{
  "title": "string",
  "description": "string",
  "parameters": {},
  "priority": "normal|high|low",
  "user_id": "string",
  "metadata": {}
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "query_id": "uuid",
    "status": "pending",
    "created_at": "2025-01-09T...",
    "estimated_completion": "2025-01-09T..."
  },
  "request_id": "uuid",
  "timestamp": "2025-01-09T..."
}
```

**Rate Limit:** 20/minute

#### 3.3 GET `/api/v1/chat/async/{query_id}/status`
**Назначение:** Получить статус асинхронного запроса

**Query Parameters:**
- `query_id` (path): string - ID асинхронного запроса

**Response:**
```json
{
  "success": true,
  "data": {
    "query_id": "uuid",
    "status": "pending|processing|completed|failed",
    "progress": 45,
    "estimated_completion": "2025-01-09T..."
  },
  "request_id": "uuid"
}
```

#### 3.4 GET `/api/v1/chat/async/{query_id}/result`
**Назначение:** Получить результат завершенного асинхронного запроса

**Response:** Полный результат (зависит от типа запроса)

#### 3.5 POST `/api/v1/chat/escalate`
**Назначение:** Эскалация к оператору-человеку

**Request:**
```json
{
  "reason": "string",
  "session_id": "string",
  "user_id": "string",
  "priority": "normal|high|urgent",
  "metadata": {}
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "escalation_id": "uuid",
    "status": "assigned",
    "estimated_response_time": "5 minutes",
    "operator_id": "string"
  },
  "request_id": "uuid"
}
```

**Rate Limit:** 20/minute

#### 3.6 GET `/api/v1/chat/async`
**Назначение:** Список асинхронных запросов пользователя

**Query Parameters:**
- `user_id`: string (обязательно)
- `status`: string (optional) - pending|processing|completed|failed
- `limit`: int (1-100, default 20)
- `offset`: int (default 0)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "query_id": "uuid",
      "title": "string",
      "status": "string",
      "created_at": "2025-01-09T..."
    }
  ],
  "request_id": "uuid",
  "metadata": {"total": 5, "limit": 20}
}
```

---

## Фаза 4: Knowledge Base - 7 эндпоинтов

### Путь: `/api/v1/kb`

#### 4.1 POST `/api/v1/kb/upload`
**Назначение:** Загрузка документов в Knowledge Base

**Request:** multipart/form-data
- `files`: UploadFile[] (PDF, DOCX, MD, TXT, CSV) - max 5 files, 50MB each
- `tags`: string (optional) - comma-separated
- `metadata`: string (optional) - JSON

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "document_id": "uuid",
      "filename": "document.pdf",
      "status": "processing",
      "chunks_count": 42,
      "size_bytes": 102400,
      "processing_id": "uuid"
    }
  ],
  "request_id": "uuid"
}
```

**Rate Limit:** 10/minute

#### 4.2 GET `/api/v1/kb`
**Назначение:** Список документов в Knowledge Base

**Query Parameters:**
- `limit`: int (1-100, default 20)
- `offset`: int (default 0)
- `status`: string (optional) - processing|completed|failed
- `tags`: string (optional) - comma-separated

**Response:** List[DocumentInfo]

#### 4.3 GET `/api/v1/kb/{document_id}`
**Назначение:** Информация о документе

**Response:**
```json
{
  "success": true,
  "data": {
    "document_id": "uuid",
    "filename": "string",
    "status": "string",
    "uploaded_at": "2025-01-09T...",
    "size_bytes": 102400,
    "chunks_count": 42,
    "metadata": {},
    "embedding_status": "pending|in_progress|completed|failed"
  },
  "request_id": "uuid"
}
```

#### 4.4 PUT `/api/v1/kb/{document_id}`
**Назначение:** Обновить информацию о документе

**Request:**
```json
{
  "filename": "new_name.pdf",
  "metadata": {"author": "John Doe"},
  "tags": ["tag1", "tag2"]
}
```

**Response:** Updated DocumentInfo

#### 4.5 DELETE `/api/v1/kb/{document_id}`
**Назначение:** Удалить документ из Knowledge Base

**Response:**
```json
{
  "success": true,
  "data": {
    "document_id": "uuid",
    "deleted_chunks": 42
  },
  "request_id": "uuid"
}
```

#### 4.6 POST `/api/v1/kb/qa-pairs/upload`
**Назначение:** Загрузить Q&A пары

**Request:**
```json
{
  "qa_pairs": [
    {
      "question": "What is this?",
      "answer": "This is...",
      "document_reference": "uuid"
    }
  ],
  "document_id": "uuid",
  "metadata": {}
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "uploaded_count": 10,
    "qa_set_id": "uuid"
  },
  "request_id": "uuid"
}
```

#### 4.7 GET `/api/v1/kb/search`
**Назначение:** Поиск по документам

**Query Parameters:**
- `query`: string (min 3 chars) - поисковой запрос
- `limit`: int (1-50, default 10)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "document_id": "uuid",
      "filename": "string",
      "relevance_score": 0.95,
      "excerpt": "text...",
      "metadata": {}
    }
  ],
  "request_id": "uuid",
  "metadata": {"query": "search", "total_found": 5}
}
```

**Rate Limit:** 30/minute

---

## Фаза 5: Intelligence - 4 эндпоинта

### Путь: `/api/v1/intelligence`

#### 5.1 POST `/api/v1/intelligence/classify-document`
**Назначение:** Классификация документа по интентам

**Request:**
```json
{
  "document_id": "uuid",
  "force_reclassify": false
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "document_id": "uuid",
    "classifications": [
      {
        "intent": "technical_support",
        "confidence": 0.95,
        "sub_category": "database",
        "reasoning": "Document contains SQL queries..."
      }
    ],
    "overall_confidence": 0.95,
    "classification_timestamp": "2025-01-09T..."
  },
  "request_id": "uuid"
}
```

#### 5.2 POST `/api/v1/intelligence/extract-metadata`
**Назначение:** Автоматическое извлечение метаданных

**Request:**
```json
{
  "document_id": "uuid",
  "fields": ["author", "date", "category"]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "document_id": "uuid",
    "extracted_metadata": [
      {
        "field_name": "author",
        "value": "John Doe",
        "confidence": 0.9,
        "type": "string"
      }
    ],
    "extraction_timestamp": "2025-01-09T..."
  },
  "request_id": "uuid"
}
```

#### 5.3 POST `/api/v1/intelligence/sentiment-analysis`
**Назначение:** Анализ тональности текста

**Request:**
```json
{
  "text": "This is amazing! I love it.",
  "language": "en"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "sentiment": "positive",
    "confidence": 0.95,
    "scores": {
      "positive": 0.95,
      "neutral": 0.04,
      "negative": 0.01
    }
  },
  "request_id": "uuid"
}
```

#### 5.4 POST `/api/v1/intelligence/extract-entities`
**Назначение:** Извлечение именованных сущностей

**Request:**
```json
{
  "text": "John Smith works at Google in San Francisco",
  "entity_types": ["PERSON", "ORG", "LOC"]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "entities": [
      {
        "text": "John Smith",
        "type": "PERSON",
        "confidence": 0.99,
        "start_pos": 0,
        "end_pos": 10
      }
    ],
    "total_entities": 3
  },
  "request_id": "uuid"
}
```

---

## Фаза 6: Taxonomy - 8 эндпоинтов

### Путь: `/api/v1/taxonomy`

#### 6.1 GET `/api/v1/taxonomy/structure`
**Назначение:** Полная структура таксономии

**Response:**
```json
{
  "success": true,
  "data": {
    "categories": [
      {
        "category_id": "uuid",
        "name": "Technical Support",
        "description": "...",
        "parent_category": null,
        "intents": ["intent_1", "intent_2"],
        "metadata": {}
      }
    ],
    "intents": [...],
    "hierarchy": {
      "category_1": ["subcategory_1", "subcategory_2"]
    }
  },
  "metadata": {"total_categories": 10, "total_intents": 50}
}
```

#### 6.2 GET `/api/v1/taxonomy/intents`
**Назначение:** Список всех интентов

**Query Parameters:**
- `category`: string (optional)
- `limit`: int (1-500, default 50)
- `offset`: int (default 0)

#### 6.3 POST `/api/v1/taxonomy/intents`
**Назначение:** Создать новый интент

**Request:**
```json
{
  "name": "password_reset",
  "description": "User wants to reset their password",
  "category": "account_management",
  "keywords": ["reset", "password", "change password"],
  "parent_intent": null
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "intent_id": "uuid",
    "name": "password_reset",
    ...
  },
  "request_id": "uuid"
}
```

#### 6.4 GET `/api/v1/taxonomy/intents/{intent_id}`
**Назначение:** Получить интент по ID

#### 6.5 PUT `/api/v1/taxonomy/intents/{intent_id}`
**Назначение:** Обновить интент

#### 6.6 DELETE `/api/v1/taxonomy/intents/{intent_id}`
**Назначение:** Удалить интент

#### 6.7 GET `/api/v1/taxonomy/categories`
**Назначение:** Список категорий

**Query Parameters:**
- `parent_only`: bool (default false)
- `limit`: int (1-500, default 50)

#### 6.8 POST `/api/v1/taxonomy/categories`
**Назначение:** Создать категорию

---

## Фаза 7: History - 6 эндпоинтов

### Путь: `/api/v1/history`

#### 7.1 GET `/api/v1/history/sessions/{session_id}`
**Назначение:** Информация о сессии

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": "uuid",
    "user_id": "uuid",
    "created_at": "2025-01-09T...",
    "ended_at": null,
    "message_count": 5,
    "status": "active",
    "duration_seconds": 120,
    "metadata": {}
  },
  "request_id": "uuid"
}
```

#### 7.2 GET `/api/v1/history/sessions/{session_id}/messages`
**Назначение:** Сообщения в сессии

**Query Parameters:**
- `limit`: int (1-500, default 50)
- `offset`: int (default 0)

#### 7.3 GET `/api/v1/history/users/{user_id}/sessions`
**Назначение:** Все сессии пользователя

**Query Parameters:**
- `status`: string (optional)
- `limit`: int (1-100, default 20)
- `offset`: int (default 0)

#### 7.4 GET `/api/v1/history/users/{user_id}/memory`
**Назначение:** Долговременная память пользователя

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "memory_id": "uuid",
      "user_id": "uuid",
      "category": "preferences",
      "key": "language",
      "value": "russian",
      "confidence": 0.95,
      "created_at": "2025-01-09T...",
      "last_updated": "2025-01-09T..."
    }
  ],
  "metadata": {"total": 5}
}
```

#### 7.5 DELETE `/api/v1/history/users/{user_id}/memory/{memory_id}`
**Назначение:** Удалить запись из памяти

#### 7.6 GET `/api/v1/history/sessions/{session_id}/summary`
**Назначение:** Автогенерированное резюме сессии

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": "uuid",
    "summary": "User asked about billing...",
    "key_points": ["payment issue", "invoice"],
    "sentiment": "frustrated",
    "generated_at": "2025-01-09T..."
  },
  "request_id": "uuid"
}
```

---

## Фаза 8: Cache Debugging - 6 эндпоинтов

### Путь: `/api/v1/cache`

#### 8.1 GET `/api/v1/cache/health`
**Назначение:** Проверка здоровья Redis

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "connection_ok": true,
    "response_time_ms": 2.5,
    "memory_available": true,
    "warnings": []
  },
  "request_id": "uuid"
}
```

#### 8.2 GET `/api/v1/cache/stats`
**Назначение:** Статистика кеша

**Response:**
```json
{
  "success": true,
  "data": {
    "total_keys": 1234,
    "memory_usage_mb": 256.5,
    "hit_rate": 0.85,
    "miss_rate": 0.15,
    "eviction_count": 10,
    "ttl_avg_seconds": 3600
  },
  "request_id": "uuid"
}
```

#### 8.3 GET `/api/v1/cache/keys`
**Назначение:** Список ключей в кеше

**Query Parameters:**
- `pattern`: string (optional) - Redis pattern (e.g., "session:*")
- `limit`: int (1-1000, default 100)

#### 8.4 GET `/api/v1/cache/keys/{key}`
**Назначение:** Значение ключа из кеша

#### 8.5 DELETE `/api/v1/cache/keys/{key}`
**Назначение:** Удалить ключ из кеша

#### 8.6 POST `/api/v1/cache/clear`
**Назначение:** Очистить кеш по pattern

**Query Parameters:**
- `pattern`: string (optional)
- `confirm`: bool (required) - должен быть true

---

## Фаза 9: System - 6 эндпоинтов

### Путь: `/api/v1/system`

#### 9.1 GET `/api/v1/system/health`
**Назначение:** Health check всей системы

**Query Parameters:**
- `detailed`: bool (default false)

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "1.0.0",
    "uptime_seconds": 86400,
    "timestamp": "2025-01-09T...",
    "components": {
      "database": "healthy",
      "redis": "healthy",
      "qdrant": "healthy",
      "pipeline": "healthy"
    }
  },
  "request_id": "uuid"
}
```

#### 9.2 GET `/api/v1/system/info`
**Назначение:** Информация о системе

**Response:**
```json
{
  "success": true,
  "data": {
    "app_name": "Support RAG",
    "version": "1.0.0",
    "environment": "production",
    "debug_mode": false,
    "start_time": "2025-01-09T10:00:00Z",
    "uptime_seconds": 86400,
    "database_connected": true,
    "redis_connected": true
  },
  "request_id": "uuid"
}
```

#### 9.3 GET `/api/v1/system/config/status`
**Назначение:** Статус конфигурации

#### 9.4 POST `/api/v1/system/config/reload`
**Назначение:** Перезагрузить конфигурацию

**Response:**
```json
{
  "success": true,
  "data": {
    "message": "Configuration reloaded successfully",
    "intents_loaded": 50,
    "categories_loaded": 10,
    "timestamp": "2025-01-09T..."
  },
  "request_id": "uuid"
}
```

#### 9.5 GET `/api/v1/system/metrics`
**Назначение:** Системные метрики

#### 9.6 POST `/api/v1/system/maintenance/warm-up`
**Назначение:** Разогреть систему

---

## Фаза 10: Channels Integration - 6 эндпоинтов

### Путь: `/api/v1/channels`

#### 10.1 POST `/api/v1/channels/telegram/send`
**Назначение:** Отправить сообщение в Telegram

**Request:**
```json
{
  "chat_id": "123456789",
  "user_id": "uuid",
  "message_text": "Hello, user!",
  "reply_to_message_id": null,
  "metadata": {}
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "message_id": 12345,
    "status": "sent",
    "timestamp": "2025-01-09T...",
    "channel": "telegram"
  },
  "request_id": "uuid"
}
```

#### 10.2 GET `/api/v1/channels/status`
**Назначение:** Статус всех каналов

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "channel": "telegram",
      "connected": true,
      "last_activity": "2025-01-09T...",
      "message_count": 1000,
      "active_users": 50,
      "error_count_1h": 2
    }
  ],
  "metadata": {"total_channels": 1}
}
```

#### 10.3 GET `/api/v1/channels/{channel}/status`
**Назначение:** Статус конкретного канала

#### 10.4 GET `/api/v1/channels/{channel}/config`
**Назначение:** Конфигурация канала

#### 10.5 PUT `/api/v1/channels/{channel}/config`
**Назначение:** Обновить конфигурацию канала

#### 10.6 POST `/api/v1/channels/{channel}/connect`
**Назначение:** Подключить канал

---

## Финальные шаги

### Фаза 11: Интеграция и документация

#### 11.1 Создать `API_EXAMPLES.md`

Содержит примеры использования всех эндпоинтов с curl команды и JSON примеры.

#### 11.2 Создать `tests/test_api_endpoints.py`

Unit тесты для:
- Health checks
- Error handling
- Rate limiting
- Request ID propagation
- Response format validation

#### 11.3 Обновить README.md

Добавить секции:
- API Documentation
- Authentication
- Rate Limits
- Error Codes
- Swagger Documentation URL

---

## Чек-лист реализации

### ✅ Этап 1: Infrastructure (Неделя 1)
- [ ] Создать `middleware.py`
- [ ] Создать `rate_limiting.py`
- [ ] Обновить `exceptions.py`
- [ ] Обновить `schemas.py` с `APIResponse`
- [ ] Обновить `main.py` приложения
- [ ] **Тестирование:** Проверить middleware работает

### ✅ Этап 2: Migration (Неделя 1-2)
- [ ] Обновить `app/api/main.py` с префиксом `/api/v1`
- [ ] Обновить все существующие эндпойнты на новый формат ответов
- [ ] Обновить `rag_routes.py`
- [ ] Обновить `admin_routes.py`
- [ ] Обновить `config_routes.py`
- [ ] Обновить `document_routes.py`
- [ ] Обновить `metadata_routes.py`
- [ ] **Тестирование:** Проверить все старые эндпойнты работают

### ✅ Этап 3: New Routes (Неделя 2-3)
- [ ] Создать `chat_routes.py` (6 эндпоинтов)
- [ ] Создать `knowledge_base_routes.py` (7 эндпоинтов)
- [ ] Создать `intelligence_routes.py` (4 эндпоинта)
- [ ] Создать `taxonomy_routes.py` (8 эндпоинтов)
- [ ] Создать `history_routes.py` (6 эндпоинтов)
- [ ] Создать `cache_routes.py` (6 эндпоинтов)
- [ ] Создать `system_routes.py` (6 эндпоинтов)
- [ ] Создать `channels_routes.py` (6 эндпоинтов)
- [ ] **Тестирование:** Все эндпойнты возвращают правильный формат

### ✅ Этап 4: Services (Неделя 3-4)
- [ ] Реализовать service методы для Chat & Generation
- [ ] Реализовать service методы для Knowledge Base
- [ ] Реализовать service методы для Intelligence
- [ ] Реализовать service методы для Taxonomy
- [ ] Реализовать service методы для History
- [ ] Реализовать service методы для Cache
- [ ] Реализовать service методы для System
- [ ] Реализовать service методы для Channels
- [ ] **Тестирование:** E2E тесты для критичных путей

### ✅ Этап 5: Testing & Docs (Неделя 4)
- [ ] Написать unit тесты для всех эндпоинтов
- [ ] Написать integration тесты
- [ ] Создать `API_EXAMPLES.md`
- [ ] Генерировать Swagger documentation
- [ ] Обновить README.md
- [ ] **Тестирование:** Все тесты проходят, Swagger доступен

### ✅ Этап 6: Deployment (Неделя 5)
- [ ] Развернуть на staging окружении
- [ ] Провести load testing (ab, wrk, etc)
- [ ] Проверить rate limiting
- [ ] Проверить error handling
- [ ] Развернуть на production
- [ ] Мониторинг метрик (Prometheus, Grafana)
- [ ] Обновить клиентов (Telegram бот, веб-интерфейс)

---

## Сводная статистика

| Компонент | Количество | Статус |
|-----------|-----------|--------|
| Новые файлы маршрутов | 8 | Создать |
| Новые файлы инфраструктуры | 2 | Создать |
| Файлы для обновления | 5 | Обновить |
| Всего эндпоинтов | 45+ | Реализовать |
| Групп эндпоинтов | 9 | - |
| Тестовые файлы | 1 | Создать |
| Документация файлы | 2 | Создать |
| **ИТОГО** | **~65 файлов** | - |

---

## Требования и зависимости

### Python пакеты
- `fastapi>=0.95.0`
- `uvicorn>=0.21.0`
- `pydantic>=1.10.0`
- `slowapi>=0.1.5` (для rate limiting)
- `psycopg[binary,asyncio]>=3.0` (PostgreSQL)
- `redis>=4.5.0` (Redis)
- `langchain>=0.0.300`
- `langfuse>=2.0.0`

### Инфраструктура
- PostgreSQL 14+ с pgvector
- Redis 6+
- Qdrant vector store

### Мониторинг
- Prometheus (опционально)
- Grafana (опционально)
- Langfuse (уже используется)

---

## Примеры успешной реализации

### До реструктуризации:
```
GET /search?q=test
GET /ask?q=test&hybrid=true
GET /health
POST /admin/refresh-intents
GET /config/system-phrases
```

### После реструктуризации:
```
GET /api/v1/system/health
POST /api/v1/chat/sync
GET /api/v1/kb/search?query=test
POST /api/v1/kb/upload
GET /api/v1/taxonomy/intents
GET /api/v1/history/sessions/{id}
GET /api/v1/cache/health
```

---

## Заключение

Этот полный план обеспечивает:

✅ **Стандартизированная архитектура** - Единый формат ответов, версионирование
✅ **Инфраструктура** - Request ID, Rate limiting, Security headers
✅ **45+ эндпоинтов** - Все требуемые функции в 9 категориях
✅ **Масштабируемость** - Легко добавить новые эндпойнты в `/api/v2/`
✅ **Документация** - Автоматическая Swagger генерация
✅ **Мониторинг** - Health checks, метрики, логирование
✅ **Безопасность** - Rate limiting, error handling, request validation

**Рекомендуемый темп:** 1-1.5 месяца для полной реализации
