# API Quick Reference Guide

**Базовый URL:** `http://localhost:8000/api/v1`

**Среда:** Закрытая корпоративная сеть (аутентификация не требуется)

**Headers:** Обязателен только `Content-Type: application/json`

---

## 📋 Все эндпоинты (45+)

### 💬 Chat & Generation (6)
| Метод | Эндпойнт | Описание |
|-------|----------|---------|
| POST | `/chat/sync` | Синхронный диалог |
| POST | `/chat/async` | Асинхронный запрос |
| GET | `/chat/async/{query_id}/status` | Статус асинхронного запроса |
| GET | `/chat/async/{query_id}/result` | Результат асинхронного запроса |
| POST | `/chat/escalate` | Эскалация к оператору |
| GET | `/chat/async` | Список асинхронных запросов |

### 📚 Knowledge Base (7)
| Метод | Эндпойнт | Описание |
|-------|----------|---------|
| POST | `/kb/upload` | Загрузить документы |
| GET | `/kb` | Список документов |
| GET | `/kb/{document_id}` | Информация о документе |
| PUT | `/kb/{document_id}` | Обновить документ |
| DELETE | `/kb/{document_id}` | Удалить документ |
| POST | `/kb/qa-pairs/upload` | Загрузить Q&A пары |
| GET | `/kb/search` | Поиск по документам |

### 🧠 Intelligence (4)
| Метод | Эндпойнт | Описание |
|-------|----------|---------|
| POST | `/intelligence/classify-document` | Классификация документа |
| POST | `/intelligence/extract-metadata` | Извлечение метаданных |
| POST | `/intelligence/sentiment-analysis` | Анализ тональности |
| POST | `/intelligence/extract-entities` | Извлечение сущностей |

### 📁 Taxonomy (8)
| Метод | Эндпойнт | Описание |
|-------|----------|---------|
| GET | `/taxonomy/structure` | Полная структура таксономии |
| GET | `/taxonomy/intents` | Список интентов |
| POST | `/taxonomy/intents` | Создать интент |
| GET | `/taxonomy/intents/{intent_id}` | Информация об интенте |
| PUT | `/taxonomy/intents/{intent_id}` | Обновить интент |
| DELETE | `/taxonomy/intents/{intent_id}` | Удалить интент |
| GET | `/taxonomy/categories` | Список категорий |
| POST | `/taxonomy/categories` | Создать категорию |

### 📜 History (6)
| Метод | Эндпойнт | Описание |
|-------|----------|---------|
| GET | `/history/sessions/{session_id}` | Информация о сессии |
| GET | `/history/sessions/{session_id}/messages` | Сообщения сессии |
| GET | `/history/users/{user_id}/sessions` | Сессии пользователя |
| GET | `/history/users/{user_id}/memory` | Память пользователя |
| DELETE | `/history/users/{user_id}/memory/{memory_id}` | Удалить память |
| GET | `/history/sessions/{session_id}/summary` | Резюме сессии |

### 🔴 Cache & Debug (6)
| Метод | Эндпойнт | Описание |
|-------|----------|---------|
| GET | `/cache/health` | Health check кеша |
| GET | `/cache/stats` | Статистика кеша |
| GET | `/cache/keys` | Список ключей |
| GET | `/cache/keys/{key}` | Значение ключа |
| DELETE | `/cache/keys/{key}` | Удалить ключ |
| POST | `/cache/clear` | Очистить кеш |

### ⚙️ System (6)
| Метод | Эндпойнт | Описание |
|-------|----------|---------|
| GET | `/system/health` | Health check всей системы |
| GET | `/system/info` | Информация о системе |
| GET | `/system/config/status` | Статус конфигурации |
| POST | `/system/config/reload` | Перезагрузить конфиг |
| GET | `/system/metrics` | Системные метрики |
| POST | `/system/maintenance/warm-up` | Разогреть систему |

### 📱 Channels Integration (6)
| Метод | Эндпойнт | Описание |
|-------|----------|---------|
| POST | `/channels/telegram/send` | Отправить в Telegram |
| GET | `/channels/status` | Статус всех каналов |
| GET | `/channels/{channel}/status` | Статус канала |
| GET | `/channels/{channel}/config` | Конфиг канала |
| PUT | `/channels/{channel}/config` | Обновить конфиг |
| POST | `/channels/{channel}/connect` | Подключить канал |

---

## 🔐 HTTP Status Codes

| Код | Значение | Описание |
|-----|----------|---------|
| 200 | OK | Успешный запрос |
| 201 | Created | Ресурс создан |
| 204 | No Content | Успешно, без контента |
| 400 | Bad Request | Ошибка в запросе |
| 401 | Unauthorized | Требуется аутентификация |
| 403 | Forbidden | Доступ запрещен |
| 404 | Not Found | Ресурс не найден |
| 409 | Conflict | Конфликт (например, дублирование) |
| 429 | Too Many Requests | Превышен rate limit |
| 500 | Internal Server Error | Ошибка сервера |
| 503 | Service Unavailable | Сервис недоступен |

---

## ⚡ Rate Limits

| Группа | Лимит | Примеры |
|--------|-------|---------|
| Chat & Generation | 20/minute | `/chat/sync`, `/chat/async` |
| Knowledge Base Search | 30/minute | `/kb/search` |
| Knowledge Base Upload | 10/minute | `/kb/upload` |
| Intelligence | 15/minute | `/intelligence/*` |
| System | 100/minute | `/system/*` |
| Cache | 50/minute | `/cache/*` |
| Default | 100/minute | Все остальные |

**Обработка Rate Limiting:**
- Статус: 429 Too Many Requests
- Header: `Retry-After: <seconds>`
- Response содержит информацию о retry

---

## 🎯 Основные сценарии использования

### 1. Диалог с пользователем
```bash
1. POST /chat/sync        # Получить ответ на вопрос
2. GET /history/sessions/{id}/messages  # Получить историю
3. GET /history/sessions/{id}/summary   # Получить резюме
```

### 2. Управление Knowledge Base
```bash
1. POST /kb/upload         # Загрузить документы
2. GET /kb                 # Список документов
3. GET /kb/search          # Поиск по KB
4. DELETE /kb/{id}         # Удалить документ
```

### 3. Анализ документов
```bash
1. POST /intelligence/classify-document    # Классифицировать
2. POST /intelligence/extract-metadata     # Извлечь метаданные
3. POST /intelligence/sentiment-analysis   # Анализ тональности
4. POST /intelligence/extract-entities     # Найти сущности
```

### 4. Управление таксономией
```bash
1. GET /taxonomy/structure         # Получить структуру
2. POST /taxonomy/intents          # Создать интент
3. GET /taxonomy/categories        # Список категорий
4. PUT /taxonomy/intents/{id}      # Обновить интент
```

### 5. Мониторинг системы
```bash
1. GET /system/health      # Проверить здоровье
2. GET /system/metrics     # Метрики
3. GET /cache/health       # Состояние кеша
4. GET /system/info        # Информация
```

### 6. Отправка сообщений
```bash
1. POST /channels/telegram/send    # Отправить в Telegram
2. GET /channels/status            # Статус каналов
```

---

## 📦 Request/Response Format

### Успешный ответ (200, 201):
```json
{
  "success": true,
  "data": { /* данные */ },
  "error": null,
  "request_id": "uuid",
  "timestamp": "2025-01-09T12:00:00Z",
  "metadata": { /* опционально */ }
}
```

### Ошибка (4xx, 5xx):
```json
{
  "success": false,
  "data": null,
  "error": "Error message",
  "error_code": "ERROR_CODE",
  "request_id": "uuid",
  "details": { /* дополнительная информация */ },
  "timestamp": "2025-01-09T12:00:00Z"
}
```

---

## 🔑 Основные параметры

### Pagination
- `limit`: int (1-500, default зависит от эндпойнта)
- `offset`: int (default 0)

### Фильтрация
- `status`: string - статус фильтр
- `category`: string - категория фильтр
- `tags`: string - теги через запятую
- `pattern`: string - Redis pattern для кеша

### Поиск
- `query`: string - поисковой запрос (min 3 chars)
- `limit`: int - максимум результатов

---

## 🛠️ Полезные инструменты

### Swagger UI
```
http://localhost:8000/docs
```

### ReDoc
```
http://localhost:8000/redoc
```

### OpenAPI Schema
```
http://localhost:8000/openapi.json
```

### Health Check
```bash
curl http://localhost:8000/api/v1/system/health
```

---

## 📌 Советы и трюки

### 1. Использовать request_id для трассировки
```bash
curl -H "X-Request-ID: my-request-123" \
     http://localhost:8000/api/v1/chat/sync
```

### 2. Проверить лимиты в headers
```bash
curl -i http://localhost:8000/api/v1/chat/sync
# Ищите headers типа: RateLimit-*, Retry-After
```

### 3. Использовать async для длительных операций
```bash
# Вместо sync (может timeout)
POST /chat/async
# Потом проверить статус
GET /chat/async/{query_id}/status
```

### 4. Всегда проверять поле `success` в ответе
```python
response = requests.post(...)
if response.json()["success"]:
    data = response.json()["data"]
else:
    error = response.json()["error"]
```

### 5. Обрабатывать retry-after для rate limiting
```python
if response.status_code == 429:
    retry_after = int(response.headers.get("Retry-After", 60))
    time.sleep(retry_after)
```

---

## 🔗 Связанные документы

- [API_DETAILED_IMPLEMENTATION_PLAN.md](./API_DETAILED_IMPLEMENTATION_PLAN.md) - Полный план реализации
- [API_EXAMPLES.md](./API_EXAMPLES.md) - Детальные примеры для каждого эндпойнта
- [API_RESTRUCTURING_PLAN.md](./API_RESTRUCTURING_PLAN.md) - Краткий план архитектуры

---

## 📞 Поддержка и контакты

При возникновении проблем:
1. Проверьте `/api/v1/system/health` - статус всех компонентов
2. Посмотрите логи приложения
3. Проверьте Swagger документацию на `/docs`
4. Создайте issue в репозитории
