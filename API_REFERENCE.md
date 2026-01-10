# API Reference - Краткий справочник

**Базовый URL:** `http://localhost:8000/api/v1`

---

## 📋 Все 30 эндпоинтов

### 💬 Chat & Generation (5)
```
POST   /chat/completions                      Синхронная генерация (полный ответ)
POST   /chat/stream                           SSE потоковая генерация (токены)
POST   /chat/escalate                         Эскалация на оператора
POST   /chat/sessions/{session_id}/escalate   Эскалация конкретной сессии
WS     /chat/ws                               WebSocket (опционально)
```

### 📚 Knowledge Base (7)
```
GET    /knowledge/contract                    Спецификация форматов
POST   /knowledge/upload                      Загрузить файл → staging
POST   /knowledge/chunks                      Добавить чанки → staging
PATCH  /knowledge/chunks                      Изменить чанки в staging
DELETE /knowledge/chunks/{chunk_id}           Удалить чанк из staging
DELETE /knowledge/files/{file_id}             Удалить файл
POST   /knowledge/commit                      Commit: staging → prod BD
```

### 🧠 Intelligence (3)
```
POST   /analysis/classify/{document_id}       Авто-классификация документа
POST   /analysis/metadata                     Сохранить результаты
PATCH  /analysis/chunks/metadata              Точечная корректировка
```

### 📁 Taxonomy (3)
```
GET    /taxonomy/tree                         Дерево категорий/интентов
PATCH  /taxonomy/rename                       Переименование с массовым обновлением
POST   /taxonomy/sync                         Синхронизировать справочник
```

### 📜 History (2)
```
GET    /history                               Получить сообщения (user_id, role, limit)
DELETE /history                               Сброс истории (hard/soft)
```

### 🔴 Cache (3)
```
GET    /cache/messages                        N последних сообщений из Redis
DELETE /cache                                 Очистить кеш (user_id или all)
GET    /cache/status                          Metrics и Memory usage
```

### ⚙️ Config (2)
```
GET    /config/full                           Полная конфигурация (с маскингом)
GET    /config/phrases                        Системные фразы и паттерны
```

### 🏥 System (2)
```
GET    /health                                Health check (DB, Redis, LLM)
GET    /ping                                  Быстрый pong для LB
```

### 📱 Channels (3)
```
POST   /channels/messages                     Отправить сообщение (без RAG)
PATCH  /channels/messages/{message_id}        Редактировать сообщение
DELETE /channels/messages/{message_id}        Удалить сообщение
```

---

## 📐 Структура ответов

### ✅ Успех
```json
{
  "data": { /* результат */ },
  "meta": {
    "trace_id": "abc-123",
    "pagination": { "limit": 20, "offset": 0, "total": 100 }
  }
}
```

### ❌ Ошибка
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": [ { "field": "name", "reason": "..." } ],
    "trace_id": "xyz-789"
  }
}
```

---

## 🔑 Ключевые особенности по плану

| Функция | Описание |
|---------|---------|
| **Staging Area** | Redis хранилище перед коммитом в БД |
| **SSE Stream** | `/chat/stream` потоковый вывод токенов |
| **Trace ID** | Идентификатор запроса для трассировки |
| **No Auth** | Закрытая сеть, аутентификация не требуется |
| **Rate Limit** | 100 req/min (общее, может быть строже) |

---

## 🎯 Основные сценарии

### 1. Диалог с пользователем
```
POST /chat/completions  → получить полный ответ
или
POST /chat/stream       → потоковый ответ по SSE
```

### 2. Загрузить документы
```
POST /knowledge/upload       → загрузить файл в staging
PATCH /knowledge/chunks      → отредактировать в staging (опционально)
POST /knowledge/commit       → commit в prod (Postgres + Qdrant)
```

### 3. Классифицировать документы
```
POST /analysis/classify/{id}  → авто-классификация
POST /analysis/metadata       → сохранить результаты
GET /taxonomy/tree            → посмотреть справочник
```

### 4. Отправить сообщение в Telegram
```
POST /channels/messages  → отправить (без RAG пайплайна)
```

---

## 💾 Фазы реализации (5)

1. **Infrastructure** - Envelope, Exception Handler, Request ID, Rate Limiter
2. **Chat & Channels** - completions, stream (SSE), escalate, telegram
3. **Knowledge** - upload, staging (Redis), commit (prod)
4. **Analysis & Taxonomy** - classify, metadata, tree, sync
5. **Remaining** - history, cache, config, system, cleanup старого

---

## 📌 Что НЕ должно быть

- ❌ `success` флаг (есть только структура data/error)
- ❌ `timestamp` в ответе
- ❌ асинхронные эндпоинты (все синхронные, кроме stream)
- ❌ аутентификация (закрытая сеть)
- ❌ embedding_status метаданные (нет в плане)

---

## 🚀 Начните отсюда

1. **Читайте:** [API_RESTRUCTURING_PLAN.md](./API_RESTRUCTURING_PLAN.md) - исходный план
2. **Планируйте:** [API_IMPLEMENTATION_PLAN.md](./API_IMPLEMENTATION_PLAN.md) - детальный план реализации
3. **Примеры:** [API_USAGE_EXAMPLES.md](./API_USAGE_EXAMPLES.md) - практические примеры

---

**Все эндпоинты, ответы и структура соответствуют исходному плану**
