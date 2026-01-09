# Примеры использования API Support RAG v1

**Базовый URL:** `http://localhost:8000/api/v1`

**Документация:** `http://localhost:8000/docs` (Swagger UI)

---

## 🔐 Аутентификация и Headers

### Обязательные Headers для всех запросов:
```bash
-H "Content-Type: application/json"
-H "X-Request-ID: req_unique_id"  # опционально, генерируется автоматически
```

### Структура ответа для всех запросов:
```json
{
  "success": true,
  "data": { /* основные данные */ },
  "error": null,
  "request_id": "abc-123-def",
  "timestamp": "2025-01-09T12:00:00Z",
  "metadata": { /* опциональные метаданные */ }
}
```

---

## 💬 Chat & Generation

### 1. Синхронный диалог

```bash
curl -X POST http://localhost:8000/api/v1/chat/sync \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Как работает система RAG?",
    "session_id": "sess_12345",
    "user_id": "user_123",
    "conversation_history": [
      {
        "role": "user",
        "content": "Привет!",
        "timestamp": "2025-01-09T11:50:00Z"
      },
      {
        "role": "assistant",
        "content": "Привет! Чем я могу помочь?",
        "timestamp": "2025-01-09T11:50:05Z"
      }
    ],
    "metadata": {
      "language": "ru",
      "device": "mobile"
    }
  }'
```

**Ответ (успех):**
```json
{
  "success": true,
  "data": {
    "message": "RAG (Retrieval-Augmented Generation) - это система, которая...",
    "sources": [
      {
        "title": "Introduction to RAG",
        "document_id": "doc_456",
        "relevance_score": 0.95,
        "excerpt": "RAG combines retrieval and generation..."
      }
    ],
    "confidence": 0.92,
    "conversation_id": "sess_12345",
    "metadata": {
      "processing_time_ms": 245,
      "model_used": "gpt-4"
    }
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 2. Асинхронный запрос (для длительных операций)

```bash
curl -X POST http://localhost:8000/api/v1/chat/async \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Анализ большого документа",
    "description": "Требует детального анализа PDF на 200 страниц",
    "parameters": {
      "max_chunks": 1000,
      "analysis_depth": "detailed"
    },
    "priority": "high",
    "user_id": "user_123",
    "metadata": {
      "source": "web_upload"
    }
  }'
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "query_id": "query_789",
    "status": "pending",
    "created_at": "2025-01-09T12:00:00Z",
    "estimated_completion": "2025-01-09T12:05:00Z"
  },
  "request_id": "req_xyz789",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 3. Проверить статус асинхронного запроса

```bash
curl -X GET "http://localhost:8000/api/v1/chat/async/query_789/status" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "query_id": "query_789",
    "status": "processing",
    "progress": 45,
    "estimated_completion": "2025-01-09T12:04:00Z"
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:15Z"
}
```

### 4. Получить результат асинхронного запроса

```bash
curl -X GET "http://localhost:8000/api/v1/chat/async/query_789/result" \
  -H "Content-Type: application/json"
```

**Ответ (когда готово):**
```json
{
  "success": true,
  "data": {
    "query_id": "query_789",
    "result": {
      "summary": "Документ содержит...",
      "key_points": [
        "Point 1",
        "Point 2"
      ],
      "analysis": "..."
    },
    "completed_at": "2025-01-09T12:05:15Z"
  },
  "request_id": "req_xyz789",
  "timestamp": "2025-01-09T12:05:15Z"
}
```

### 5. Эскалация к оператору

```bash
curl -X POST http://localhost:8000/api/v1/chat/escalate \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Нужна помощь с техническим вопросом",
    "session_id": "sess_12345",
    "user_id": "user_123",
    "priority": "high",
    "metadata": {
      "issue_type": "billing"
    }
  }'
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "escalation_id": "esc_123",
    "status": "assigned",
    "estimated_response_time": "5 minutes",
    "operator_id": "op_456",
    "operator_name": "John Doe"
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 6. Список асинхронных запросов пользователя

```bash
curl -X GET "http://localhost:8000/api/v1/chat/async?user_id=user_123&status=completed&limit=10&offset=0" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": [
    {
      "query_id": "query_789",
      "title": "Анализ документа",
      "status": "completed",
      "created_at": "2025-01-09T11:00:00Z",
      "completed_at": "2025-01-09T11:05:15Z"
    }
  ],
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z",
  "metadata": {
    "total": 5,
    "limit": 10,
    "offset": 0
  }
}
```

---

## 📚 Knowledge Base

### 1. Загрузить документы

```bash
curl -X POST http://localhost:8000/api/v1/kb/upload \
  -F "files=@/path/to/document.pdf" \
  -F "files=@/path/to/guide.docx" \
  -F "tags=documentation,tutorial,important" \
  -F 'metadata={"author":"John Doe","department":"Support"}'
```

**Ответ:**
```json
{
  "success": true,
  "data": [
    {
      "document_id": "doc_456",
      "filename": "document.pdf",
      "status": "processing",
      "chunks_count": 42,
      "size_bytes": 1024000,
      "processing_id": "proc_123"
    },
    {
      "document_id": "doc_789",
      "filename": "guide.docx",
      "status": "processing",
      "chunks_count": 28,
      "size_bytes": 512000,
      "processing_id": "proc_124"
    }
  ],
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 2. Список документов в Knowledge Base

```bash
curl -X GET "http://localhost:8000/api/v1/kb?limit=20&offset=0&status=completed&tags=documentation" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": [
    {
      "document_id": "doc_456",
      "filename": "document.pdf",
      "status": "completed",
      "uploaded_at": "2025-01-09T10:00:00Z",
      "size_bytes": 1024000,
      "chunks_count": 42,
      "metadata": {
        "author": "John Doe"
      },
      "embedding_status": "completed"
    }
  ],
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z",
  "metadata": {
    "total": 5,
    "limit": 20,
    "offset": 0
  }
}
```

### 3. Информация о документе

```bash
curl -X GET "http://localhost:8000/api/v1/kb/doc_456" \
  -H "Content-Type: application/json"
```

### 4. Обновить документ

```bash
curl -X PUT http://localhost:8000/api/v1/kb/doc_456 \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "new_name.pdf",
    "metadata": {
      "author": "Jane Doe",
      "version": "2.0"
    },
    "tags": ["v2", "updated", "important"]
  }'
```

### 5. Удалить документ

```bash
curl -X DELETE "http://localhost:8000/api/v1/kb/doc_456" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "document_id": "doc_456",
    "deleted_chunks": 42
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 6. Загрузить Q&A пары

```bash
curl -X POST http://localhost:8000/api/v1/kb/qa-pairs/upload \
  -H "Content-Type: application/json" \
  -d '{
    "qa_pairs": [
      {
        "question": "Как сбросить пароль?",
        "answer": "Перейдите в настройки, нажмите 'Забыли пароль?'...",
        "document_reference": "doc_456"
      },
      {
        "question": "Как связаться с поддержкой?",
        "answer": "Вы можете связаться с нами через...",
        "document_reference": "doc_789"
      }
    ],
    "document_id": "doc_456",
    "metadata": {
      "source": "manual_entry"
    }
  }'
```

### 7. Поиск по Knowledge Base

```bash
curl -X GET "http://localhost:8000/api/v1/kb/search?query=как%20сбросить%20пароль&limit=10" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": [
    {
      "document_id": "doc_456",
      "filename": "faq.pdf",
      "relevance_score": 0.98,
      "excerpt": "Как сбросить пароль: Перейдите в настройки и нажмите...",
      "metadata": {
        "page": 5
      }
    }
  ],
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z",
  "metadata": {
    "query": "как сбросить пароль",
    "total_found": 5
  }
}
```

---

## 🧠 Intelligence

### 1. Классификация документа

```bash
curl -X POST http://localhost:8000/api/v1/intelligence/classify-document \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "doc_456",
    "force_reclassify": false
  }'
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "document_id": "doc_456",
    "classifications": [
      {
        "intent": "technical_support",
        "confidence": 0.95,
        "sub_category": "database",
        "reasoning": "Document содержит SQL queries и ошибки базы данных"
      }
    ],
    "overall_confidence": 0.95,
    "classification_timestamp": "2025-01-09T12:00:00Z"
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 2. Извлечение метаданных

```bash
curl -X POST http://localhost:8000/api/v1/intelligence/extract-metadata \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "doc_456",
    "fields": ["author", "date", "category"]
  }'
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "document_id": "doc_456",
    "extracted_metadata": [
      {
        "field_name": "author",
        "value": "John Doe",
        "confidence": 0.95,
        "type": "string"
      },
      {
        "field_name": "date",
        "value": "2025-01-09",
        "confidence": 0.92,
        "type": "date"
      }
    ],
    "extraction_timestamp": "2025-01-09T12:00:00Z"
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 3. Анализ тональности

```bash
curl -X POST http://localhost:8000/api/v1/intelligence/sentiment-analysis \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Это потрясающе! Мне очень нравится эта система, она работает отлично!",
    "language": "ru"
  }'
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "sentiment": "positive",
    "confidence": 0.98,
    "scores": {
      "positive": 0.98,
      "neutral": 0.01,
      "negative": 0.01
    }
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 4. Извлечение сущностей

```bash
curl -X POST http://localhost:8000/api/v1/intelligence/extract-entities \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Иван Петров работает в компании Google в Москве с 2020 года",
    "entity_types": ["PERSON", "ORG", "LOC", "DATE"]
  }'
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "entities": [
      {
        "text": "Иван Петров",
        "type": "PERSON",
        "confidence": 0.99,
        "start_pos": 0,
        "end_pos": 11
      },
      {
        "text": "Google",
        "type": "ORG",
        "confidence": 0.99,
        "start_pos": 24,
        "end_pos": 30
      },
      {
        "text": "Москве",
        "type": "LOC",
        "confidence": 0.95,
        "start_pos": 34,
        "end_pos": 40
      },
      {
        "text": "2020",
        "type": "DATE",
        "confidence": 0.99,
        "start_pos": 48,
        "end_pos": 52
      }
    ],
    "total_entities": 4
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

---

## 📁 Taxonomy

### 1. Получить структуру таксономии

```bash
curl -X GET "http://localhost:8000/api/v1/taxonomy/structure" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "categories": [
      {
        "category_id": "cat_1",
        "name": "Техническая поддержка",
        "description": "Вопросы, связанные с технической поддержкой",
        "parent_category": null,
        "intents": ["intent_1", "intent_2"],
        "metadata": {}
      }
    ],
    "intents": [
      {
        "intent_id": "intent_1",
        "name": "password_reset",
        "description": "Пользователь хочет сбросить пароль",
        "category": "account_management",
        "keywords": ["пароль", "сброс", "забыли"],
        "parent_intent": null,
        "metadata": {}
      }
    ],
    "hierarchy": {
      "cat_1": ["cat_1_1", "cat_1_2"]
    }
  },
  "metadata": {
    "total_categories": 5,
    "total_intents": 25
  }
}
```

### 2. Список интентов

```bash
curl -X GET "http://localhost:8000/api/v1/taxonomy/intents?category=account_management&limit=20&offset=0" \
  -H "Content-Type: application/json"
```

### 3. Создать интент

```bash
curl -X POST http://localhost:8000/api/v1/taxonomy/intents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "billing_inquiry",
    "description": "Пользователь имеет вопросы о счетах и платежах",
    "category": "billing",
    "keywords": ["счет", "платеж", "цена", "стоимость"],
    "parent_intent": null
  }'
```

### 4. Список категорий

```bash
curl -X GET "http://localhost:8000/api/v1/taxonomy/categories?parent_only=true&limit=50" \
  -H "Content-Type: application/json"
```

---

## 📜 History

### 1. Информация о сессии

```bash
curl -X GET "http://localhost:8000/api/v1/history/sessions/sess_12345" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "session_id": "sess_12345",
    "user_id": "user_123",
    "created_at": "2025-01-09T11:00:00Z",
    "ended_at": null,
    "message_count": 5,
    "status": "active",
    "duration_seconds": 3600,
    "metadata": {}
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 2. Сообщения в сессии

```bash
curl -X GET "http://localhost:8000/api/v1/history/sessions/sess_12345/messages?limit=50&offset=0" \
  -H "Content-Type: application/json"
```

### 3. Все сессии пользователя

```bash
curl -X GET "http://localhost:8000/api/v1/history/users/user_123/sessions?status=active&limit=20&offset=0" \
  -H "Content-Type: application/json"
```

### 4. Долговременная память пользователя

```bash
curl -X GET "http://localhost:8000/api/v1/history/users/user_123/memory?category=preferences" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": [
    {
      "memory_id": "mem_1",
      "user_id": "user_123",
      "category": "preferences",
      "key": "language",
      "value": "russian",
      "confidence": 0.95,
      "created_at": "2025-01-05T10:00:00Z",
      "last_updated": "2025-01-08T15:30:00Z",
      "metadata": {}
    }
  ],
  "metadata": {
    "total": 3
  }
}
```

### 5. Удалить запись из памяти

```bash
curl -X DELETE "http://localhost:8000/api/v1/history/users/user_123/memory/mem_1" \
  -H "Content-Type: application/json"
```

### 6. Резюме сессии

```bash
curl -X GET "http://localhost:8000/api/v1/history/sessions/sess_12345/summary" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "session_id": "sess_12345",
    "summary": "Пользователь спрашивал о способах сброса пароля и проблемах с входом...",
    "key_points": [
      "Забыл пароль",
      "Не приходит письмо восстановления",
      "Ошибка при входе"
    ],
    "sentiment": "neutral",
    "generated_at": "2025-01-09T12:00:00Z"
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

---

## 🔴 Cache & Debug

### 1. Health Check кеша

```bash
curl -X GET "http://localhost:8000/api/v1/cache/health" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "connection_ok": true,
    "response_time_ms": 2.1,
    "memory_available": true,
    "warnings": []
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 2. Статистика кеша

```bash
curl -X GET "http://localhost:8000/api/v1/cache/stats" \
  -H "Content-Type: application/json"
```

**Ответ:**
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
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 3. Список ключей в кеше

```bash
curl -X GET "http://localhost:8000/api/v1/cache/keys?pattern=session:*&limit=100" \
  -H "Content-Type: application/json"
```

### 4. Значение ключа

```bash
curl -X GET "http://localhost:8000/api/v1/cache/keys/session:sess_12345" \
  -H "Content-Type: application/json"
```

### 5. Удалить ключ

```bash
curl -X DELETE "http://localhost:8000/api/v1/cache/keys/session:sess_12345" \
  -H "Content-Type: application/json"
```

### 6. Очистить кеш

```bash
curl -X POST "http://localhost:8000/api/v1/cache/clear?pattern=session:*&confirm=true" \
  -H "Content-Type: application/json"
```

---

## ⚙️ System

### 1. Health Check

```bash
curl -X GET "http://localhost:8000/api/v1/system/health?detailed=true" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "1.0.0",
    "uptime_seconds": 86400,
    "timestamp": "2025-01-09T12:00:00Z",
    "components": {
      "database": "healthy",
      "redis": "healthy",
      "qdrant": "healthy",
      "pipeline": "healthy",
      "langfuse": "healthy"
    }
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 2. Информация о системе

```bash
curl -X GET "http://localhost:8000/api/v1/system/info" \
  -H "Content-Type: application/json"
```

### 3. Статус конфигурации

```bash
curl -X GET "http://localhost:8000/api/v1/system/config/status" \
  -H "Content-Type: application/json"
```

### 4. Перезагрузить конфигурацию

```bash
curl -X POST "http://localhost:8000/api/v1/system/config/reload" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "message": "Configuration reloaded successfully",
    "intents_loaded": 50,
    "categories_loaded": 10,
    "timestamp": "2025-01-09T12:00:00Z"
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 5. Метрики системы

```bash
curl -X GET "http://localhost:8000/api/v1/system/metrics" \
  -H "Content-Type: application/json"
```

---

## 📱 Channels Integration

### 1. Отправить сообщение в Telegram

```bash
curl -X POST http://localhost:8000/api/v1/channels/telegram/send \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "123456789",
    "user_id": "user_123",
    "message_text": "Здравствуйте! Я помощник поддержки. Чем я могу помочь?",
    "reply_to_message_id": null,
    "metadata": {
      "message_type": "greeting"
    }
  }'
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "message_id": 12345,
    "status": "sent",
    "timestamp": "2025-01-09T12:00:00Z",
    "channel": "telegram"
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### 2. Статус всех каналов

```bash
curl -X GET "http://localhost:8000/api/v1/channels/status" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "success": true,
  "data": [
    {
      "channel": "telegram",
      "connected": true,
      "last_activity": "2025-01-09T12:00:00Z",
      "message_count": 1000,
      "active_users": 50,
      "error_count_1h": 0
    }
  ],
  "metadata": {
    "total_channels": 1
  }
}
```

### 3. Статус конкретного канала

```bash
curl -X GET "http://localhost:8000/api/v1/channels/telegram/status" \
  -H "Content-Type: application/json"
```

### 4. Конфигурация канала

```bash
curl -X GET "http://localhost:8000/api/v1/channels/telegram/config" \
  -H "Content-Type: application/json"
```

### 5. Обновить конфигурацию канала

```bash
curl -X PUT http://localhost:8000/api/v1/channels/telegram/config \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "telegram",
    "enabled": true,
    "webhook_url": "https://api.example.com/telegram",
    "rate_limit": 100,
    "metadata": {
      "bot_token": "****"
    }
  }'
```

### 6. Подключить канал

```bash
curl -X POST "http://localhost:8000/api/v1/channels/telegram/connect" \
  -H "Content-Type: application/json" \
  -d '{
    "credentials": {
      "bot_token": "your_bot_token_here",
      "webhook_url": "https://api.example.com/telegram"
    }
  }'
```

---

## 🔧 Общие примеры

### Обработка ошибок

**Пример ошибки (400 Bad Request):**
```bash
curl -X POST http://localhost:8000/api/v1/chat/sync \
  -H "Content-Type: application/json" \
  -d '{
    "message": "",
    "session_id": "",
    "user_id": ""
  }'
```

**Ответ ошибки:**
```json
{
  "success": false,
  "error": "Message cannot be empty",
  "error_code": "VALIDATION_ERROR",
  "request_id": "req_abc123",
  "details": {
    "field": "message"
  },
  "timestamp": "2025-01-09T12:00:00Z"
}
```

### Rate Limiting

Когда превышен лимит, вернется 429:

```json
{
  "success": false,
  "error": "Rate limit exceeded",
  "retry_after": "20",
  "timestamp": "2025-01-09T12:00:00Z"
}
```

---

## 📊 Используемые инструменты

### Для тестирования API:

**1. curl (встроенный инструмент):**
```bash
curl -X GET "http://localhost:8000/api/v1/system/health"
```

**2. Postman:**
- Импортировать: `http://localhost:8000/openapi.json`
- Использовать для интерактивного тестирования

**3. Swagger UI (встроенный):**
- Перейти на `http://localhost:8000/docs`

**4. Python requests:**
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/chat/sync",
    json={
        "message": "Hello",
        "session_id": "sess_123",
        "user_id": "user_123"
    }
)
print(response.json())
```

**5. JavaScript fetch:**
```javascript
fetch('http://localhost:8000/api/v1/system/health')
  .then(r => r.json())
  .then(data => console.log(data))
```

---

## 🎯 Чек-лист при интеграции

- [ ] API доступен на `http://localhost:8000/api/v1`
- [ ] Swagger документация работает на `/docs`
- [ ] Все запросы возвращают правильный формат с `request_id`
- [ ] Rate limiting работает
- [ ] Ошибки обрабатываются правильно
- [ ] Request ID пропагируется во все response
- [ ] Логирование работает
- [ ] Health check возвращает статус всех компонентов
