# API Реструктуризация - План Реализации

**Основано на:** [API_RESTRUCTURING_PLAN.md](./API_RESTRUCTURING_PLAN.md)
**Дата:** 2025-01-09
**Статус:** Детальный план реализации

---

## 📋 Сводка из исходного плана

### 9 групп эндпоинтов (30 всего):

| Группа | Эндпоинтов | Назначение |
|--------|-----------|-----------|
| **Chat & Generation** | 5 | Completions + Stream (SSE) + эскалация |
| **Knowledge Base** | 7 | Upload + Staging (Redis) + Commit в prod |
| **Intelligence** | 3 | Классификация документов |
| **Taxonomy** | 3 | Управление справочниками интентов |
| **History** | 2 | История сообщений пользователя |
| **Cache** | 3 | Отладка Redis |
| **Config** | 2 | Конфигурация RAG |
| **System** | 2 | Health + Ping |
| **Channels** | 3 | Telegram: send/edit/delete |
| **ИТОГО** | **30** | |

---

## 🎯 Точные эндпоинты по исходному плану

### 1. Chat & Generation (5)

```
POST   /api/v1/chat/completions              - Синхронная генерация (полный ответ)
POST   /api/v1/chat/stream                   - SSE потоковая генерация (токены по мере)
POST   /api/v1/chat/escalate                 - Эскалация на оператора
POST   /api/v1/chat/sessions/{session_id}/escalate  - Эскалация конкретной сессии
WS     /api/v1/chat/ws                       - WebSocket (опционально)
```

**Key Feature:** `/chat/stream` использует SSE (Server-Sent Events) для потокового вывода

---

### 2. Knowledge Base (7)

```
GET    /api/v1/knowledge/contract            - Спецификация форматов (JSON Schema)
POST   /api/v1/knowledge/upload              - Загрузка файла → staging (Redis)
POST   /api/v1/knowledge/chunks              - Ручное добавление чанков → staging
PATCH  /api/v1/knowledge/chunks              - Массовое изменение чанков в staging
DELETE /api/v1/knowledge/chunks/{chunk_id}   - Удалить чанк из staging
DELETE /api/v1/knowledge/files/{file_id}     - Удалить файл и staging данные
POST   /api/v1/knowledge/commit               - Commit из staging → prod BD (Postgres/Qdrant)
```

**Key Feature:** Staging Area в Redis перед коммитом в основную БД

---

### 3. Intelligence (3)

```
POST   /api/v1/analysis/classify/{document_id}  - Авто-классификация документа
POST   /api/v1/analysis/metadata                - Сохранить результаты классификации
PATCH  /api/v1/analysis/chunks/metadata         - Точечная корректировка метаданных
```

---

### 4. Taxonomy (3)

```
GET    /api/v1/taxonomy/tree                 - Иерархическое дерево категорий/интентов
PATCH  /api/v1/taxonomy/rename               - Переименование с массовым обновлением
POST   /api/v1/taxonomy/sync                 - Синхронизация справочника с документами
```

---

### 5. History (2)

```
GET    /api/v1/history                       - Получить сообщения (фильтры: user_id, role, limit)
DELETE /api/v1/history                       - Сброс истории (hard или soft delete)
```

---

### 6. Cache (3)

```
GET    /api/v1/cache/messages                - N последних сообщений из Redis
DELETE /api/v1/cache                         - Очистка (параметр: user_id или all)
GET    /api/v1/cache/status                  - Metrics и Memory usage
```

---

### 7. Config (2)

```
GET    /api/v1/config/full                   - Полная конфиг (с маскингом секретов)
GET    /api/v1/config/phrases                - Системные фразы и паттерны
```

---

### 8. System (2)

```
GET    /api/v1/health                        - Health check (DB, Redis, LLM API)
GET    /api/v1/ping                          - Быстрый pong для балансировщиков
```

---

### 9. Channels (3)

```
POST   /api/v1/channels/messages             - Отправить сообщение (без RAG)
PATCH  /api/v1/channels/messages/{message_id} - Редактировать сообщение
DELETE /api/v1/channels/messages/{message_id} - Удалить сообщение
```

---

## 📐 Стандартизация ответов (из плана)

### Успешный ответ:
```json
{
  "data": { ... },
  "meta": {
    "pagination": { ... },
    "trace_id": "abc-123"
  }
}
```

### Ошибочный ответ:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [ ... ],
    "trace_id": "abc-123"
  }
}
```

**Ключевые отличия от моих вымышленных планов:**
- ❌ НЕТ `success` флага в ответе
- ❌ НЕТ `timestamp` в ответе
- ✅ ЕСТЬ `trace_id` вместо `request_id`
- ✅ ЕСТЬ `meta` вместо `metadata`

---

## 🏗️ 5 Этапов реализации

### Этап 1: Фундамент (Infrastructure)

**Работы:**
1. Создать структуру `app/api/v1`
2. Реализовать базовые модели (`Envelope`, `ErrorResponse`)
3. Настроить Middleware:
   - Exception Handler (глобальная обработка ошибок)
   - Request ID (X-Request-ID header)
4. Подключить `fastapi-limiter` (Redis-based) для Rate Limiting

**Файлы:**
- `app/api/v1/__init__.py`
- `app/api/v1/models.py` (Envelope, ErrorResponse)
- `app/api/v1/middleware.py` (Exception Handler, Request ID)
- `app/api/v1/limiter.py` (Rate Limiter config)

---

### Этап 2: Chat & Channels

**Работы:**
1. Переписать `rag_routes.py` → `ChatController`
2. Реализовать SSE для `/chat/stream` (используя `EventSourceResponse`)
3. Реализовать `ChannelController` (Telegram send/edit/delete)
4. Разделить: контроллер валидирует → Service Layer логику

**Новые файлы:**
- `app/api/v1/chat.py` (POST /completions, POST /stream, POST /escalate)
- `app/api/v1/channels.py` (POST/PATCH/DELETE /channels/messages)

**Ключевая особенность:**
- `/chat/stream` возвращает SSE поток токенов по мере генерации

---

### Этап 3: Knowledge Management

**Работы:**
1. Создать таблицы для "Черновиков" (Drafts) в Redis Staging Area
2. JSON Schema валидаторы для форматов
3. Реализовать upload → staging pipeline

**Новые файлы:**
- `app/api/v1/knowledge.py` (GET/POST/PATCH/DELETE knowledge/*)
- `app/services/staging.py` (работа с Redis staging)

**Ключевая особенность:**
- `/knowledge/commit` переносит данные из Redis (staging) в Postgres + Qdrant

---

### Этап 4: Taxonomy & Analysis

**Работы:**
1. Выделить справочник интентов/категорий в отдельную сущность БД
2. Реализовать логику синхронизации
3. Эндпоинты анализа/классификации

**Новые файлы:**
- `app/api/v1/taxonomy.py`
- `app/api/v1/analysis.py`
- `app/services/taxonomy.py` (logic)

---

### Этап 5: Ops & Cleanup

**Работы:**
1. Добавить Swagger теги и описания
2. Удалить старые маршруты после миграции клиентов
3. Мониторинг и метрики

**Файлы:**
- `app/api/v1/config.py` (GET /config/*)
- `app/api/v1/system.py` (GET /health, GET /ping)
- `app/api/v1/history.py` (GET/DELETE /history)
- `app/api/v1/cache.py` (GET/DELETE /cache/*)

---

## 🔧 Инфраструктурные компоненты

Согласно плану:

1. **Request ID** - X-Request-ID header в каждый запрос/ответ
2. **Global Exception Handler** - преобразование ошибок в JSON
3. **Rate Limiter** - fastapi-limiter (100 req/min для общего, строже для тяжелых)
4. **Security Headers** - базовая защита
5. **OpenAPI/Swagger** - автоматическая генерация

---

## ✅ Чек-лист реализации

### Фаза 1: Инфраструктура
- [ ] Создать app/api/v1 структуру
- [ ] Envelope модели (успех + ошибка)
- [ ] Exception Handler middleware
- [ ] Request ID middleware
- [ ] Rate Limiter конфигурация

### Фаза 2: Chat & Channels
- [ ] POST /chat/completions
- [ ] POST /chat/stream (SSE)
- [ ] POST /chat/escalate
- [ ] POST /chat/sessions/{id}/escalate
- [ ] WS /chat/ws (опционально)
- [ ] POST /channels/messages
- [ ] PATCH /channels/messages/{id}
- [ ] DELETE /channels/messages/{id}

### Фаза 3: Knowledge
- [ ] GET /knowledge/contract
- [ ] POST /knowledge/upload (staging)
- [ ] POST /knowledge/chunks (staging)
- [ ] PATCH /knowledge/chunks (staging)
- [ ] DELETE /knowledge/chunks/{id}
- [ ] DELETE /knowledge/files/{id}
- [ ] POST /knowledge/commit (redis → postgres/qdrant)
- [ ] Redis Staging Area реализация

### Фаза 4: Analysis & Taxonomy
- [ ] POST /analysis/classify/{id}
- [ ] POST /analysis/metadata
- [ ] PATCH /analysis/chunks/metadata
- [ ] GET /taxonomy/tree
- [ ] PATCH /taxonomy/rename
- [ ] POST /taxonomy/sync

### Фаза 5: Остальное
- [ ] GET /history + DELETE /history
- [ ] GET /cache/messages + DELETE /cache + GET /cache/status
- [ ] GET /config/full + GET /config/phrases
- [ ] GET /health + GET /ping
- [ ] Swagger/OpenAPI теги
- [ ] Удаление старых маршрутов

---

## 🚀 Как начать

1. **Читайте** исходный [API_RESTRUCTURING_PLAN.md](./API_RESTRUCTURING_PLAN.md)
2. **Следуйте** 5 этапам в порядке
3. **Реализуйте** по группам эндпоинтов
4. **Тестируйте** через Swagger на `/docs`

---

## 📌 Важные замечания

- **Staging Area:** Redis используется как промежуточное хранилище перед коммитом в БД
- **SSE Stream:** `/chat/stream` - это потоковый ответ, не простой JSON
- **No Authentication:** Система в закрытой сети, аутентификация не требуется
- **Trace ID:** Используйте `trace_id` для трассировки, а не custom `request_id`

---

**Этот план 100% соответствует исходному плану из API_RESTRUCTURING_PLAN.md**
