# Примеры использования API Support RAG

**Основано на:** [API_RESTRUCTURING_PLAN.md](./API_RESTRUCTURING_PLAN.md)
**Базовый URL:** `http://localhost:8000/api/v1`

---

## 📐 Структура ответов

### Успешный ответ (2xx)
```json
{
  "data": {
    "answer": "...",
    "sources": [...]
  },
  "meta": {
    "trace_id": "abc-123",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 100
    }
  }
}
```

### Ошибка (4xx, 5xx)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "question",
        "reason": "Cannot be empty"
      }
    ],
    "trace_id": "xyz-789"
  }
}
```

---

## 💬 Chat & Generation

### 1. Синхронная генерация (completions)

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Как работает система?",
    "session_id": "sess_123",
    "user_id": "user_456",
    "conversation_history": [
      {"role": "user", "content": "Привет"},
      {"role": "assistant", "content": "Привет! Чем помочь?"}
    ]
  }'
```

**Ответ:**
```json
{
  "data": {
    "answer": "Система работает следующим образом...",
    "sources": [
      {
        "document_id": "doc_123",
        "title": "README.md",
        "excerpt": "..."
      }
    ]
  },
  "meta": {
    "trace_id": "req-abc-123"
  }
}
```

---

### 2. Потоковая генерация (SSE stream)

```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Расскажи подробно",
    "session_id": "sess_123",
    "user_id": "user_456"
  }'
```

**Ответ (Server-Sent Events):**
```
data: {"token": "Система", "trace_id": "req-abc"}
data: {"token": " работает", "trace_id": "req-abc"}
data: {"token": " следующим", "trace_id": "req-abc"}
...
data: {"token": "[DONE]", "trace_id": "req-abc"}
```

**Чтение в Python:**
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/chat/stream",
    json={"question": "...", "session_id": "...", "user_id": "..."},
    stream=True
)

for line in response.iter_lines():
    if line:
        data = json.loads(line.decode().replace('data: ', ''))
        print(data['token'], end='', flush=True)
```

---

### 3. Эскалация на оператора

```bash
curl -X POST http://localhost:8000/api/v1/chat/escalate \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_123",
    "reason": "Нужна помощь оператора"
  }'
```

---

## 📚 Knowledge Base

### 1. Получить спецификацию форматов

```bash
curl -X GET http://localhost:8000/api/v1/knowledge/contract
```

**Ответ:**
```json
{
  "data": {
    "supported_formats": ["json", "pdf", "csv", "md"],
    "max_pairs": 100,
    "max_question_length": 500,
    "max_answer_length": 5000,
    "json_schema": { ... }
  },
  "meta": {
    "trace_id": "req-xyz"
  }
}
```

---

### 2. Загрузить файл → Staging

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/upload \
  -F "file=@questions.pdf"
```

**Ответ:**
```json
{
  "data": {
    "file_id": "file_789",
    "draft_id": "draft_456",
    "extracted_pairs": [
      {"question": "Q1?", "answer": "A1"},
      {"question": "Q2?", "answer": "A2"}
    ],
    "total_pairs": 2
  },
  "meta": {
    "trace_id": "req-abc"
  }
}
```

---

### 3. Добавить чанки вручную → Staging

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/chunks \
  -H "Content-Type: application/json" \
  -d '{
    "draft_id": "draft_456",
    "chunks": [
      {
        "question": "Что такое RAG?",
        "answer": "RAG это...",
        "metadata": {"source": "manual"}
      }
    ]
  }'
```

---

### 4. Отредактировать чанки в Staging

```bash
curl -X PATCH http://localhost:8000/api/v1/knowledge/chunks \
  -H "Content-Type: application/json" \
  -d '{
    "draft_id": "draft_456",
    "updates": [
      {
        "chunk_id": "chunk_1",
        "question": "Что такое RAG? (отредактировано)"
      }
    ]
  }'
```

---

### 5. Коммитить из Staging → Prod BD

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/commit \
  -H "Content-Type: application/json" \
  -d '{
    "draft_id": "draft_456",
    "action": "commit"
  }'
```

**Результат:** Данные переходят из Redis (staging) в Postgres + Qdrant (prod)

---

## 🧠 Intelligence

### 1. Классифицировать документ

```bash
curl -X POST http://localhost:8000/api/v1/analysis/classify/doc_123
```

**Ответ:**
```json
{
  "data": {
    "document_id": "doc_123",
    "classifications": [
      {
        "intent": "technical_support",
        "category": "database",
        "confidence": 0.95
      }
    ]
  },
  "meta": {
    "trace_id": "req-abc"
  }
}
```

---

### 2. Сохранить результаты классификации

```bash
curl -X POST http://localhost:8000/api/v1/analysis/metadata \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "doc_123",
    "metadata": {
      "intent": "technical_support",
      "category": "database",
      "tags": ["urgent", "sql"]
    }
  }'
```

---

## 📁 Taxonomy

### 1. Получить дерево интентов/категорий

```bash
curl -X GET http://localhost:8000/api/v1/taxonomy/tree
```

**Ответ:**
```json
{
  "data": {
    "categories": {
      "technical_support": {
        "name": "Техническая поддержка",
        "intents": [
          "database_error",
          "connection_issue",
          "performance"
        ]
      },
      "billing": {
        "name": "Выставление счетов",
        "intents": ["invoice", "payment"]
      }
    }
  },
  "meta": {
    "trace_id": "req-xyz"
  }
}
```

---

### 2. Переименовать категорию (с массовым обновлением)

```bash
curl -X PATCH http://localhost:8000/api/v1/taxonomy/rename \
  -H "Content-Type: application/json" \
  -d '{
    "old_name": "technical_support",
    "new_name": "tech_help"
  }'
```

---

### 3. Синхронизировать справочник с документами

```bash
curl -X POST http://localhost:8000/api/v1/taxonomy/sync
```

---

## 📜 History

### 1. Получить историю пользователя

```bash
curl -X GET "http://localhost:8000/api/v1/history?user_id=user_456&limit=20"
```

**Ответ:**
```json
{
  "data": [
    {
      "message_id": "msg_1",
      "role": "user",
      "content": "Привет",
      "timestamp": "2025-01-09T10:00:00Z"
    },
    {
      "message_id": "msg_2",
      "role": "assistant",
      "content": "Привет! Чем помочь?",
      "timestamp": "2025-01-09T10:00:05Z"
    }
  ],
  "meta": {
    "trace_id": "req-abc",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 150
    }
  }
}
```

---

### 2. Сбросить историю

```bash
curl -X DELETE http://localhost:8000/api/v1/history \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_456",
    "method": "soft"  # или "hard" для полного удаления
  }'
```

---

## 🔴 Cache

### 1. Получить последние сообщения из Redis

```bash
curl -X GET "http://localhost:8000/api/v1/cache/messages?user_id=user_456&limit=10"
```

---

### 2. Очистить кеш

```bash
curl -X DELETE http://localhost:8000/api/v1/cache \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_456"  # или "all" для полной очистки
  }'
```

---

### 3. Статус кеша

```bash
curl -X GET http://localhost:8000/api/v1/cache/status
```

**Ответ:**
```json
{
  "data": {
    "memory_usage_mb": 256,
    "total_keys": 1500,
    "hit_rate": 0.85,
    "connected": true
  },
  "meta": {
    "trace_id": "req-xyz"
  }
}
```

---

## ⚙️ System

### 1. Health Check

```bash
curl -X GET http://localhost:8000/api/v1/health
```

**Ответ:**
```json
{
  "data": {
    "status": "healthy",
    "database": "ok",
    "redis": "ok",
    "llm_api": "ok"
  },
  "meta": {
    "trace_id": "req-abc"
  }
}
```

---

### 2. Ping

```bash
curl -X GET http://localhost:8000/api/v1/ping
```

**Ответ:**
```json
{
  "data": "pong",
  "meta": {
    "trace_id": "req-xyz"
  }
}
```

---

## 📱 Channels (Telegram)

### 1. Отправить сообщение

```bash
curl -X POST http://localhost:8000/api/v1/channels/messages \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "telegram",
    "user_id": "user_456",
    "message": "Привет от системы!"
  }'
```

**Ответ:**
```json
{
  "data": {
    "message_id": "msg_123",
    "status": "sent"
  },
  "meta": {
    "trace_id": "req-abc"
  }
}
```

---

### 2. Отредактировать сообщение

```bash
curl -X PATCH http://localhost:8000/api/v1/channels/messages/msg_123 \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Привет от системы! (отредактировано)"
  }'
```

---

### 3. Удалить сообщение

```bash
curl -X DELETE http://localhost:8000/api/v1/channels/messages/msg_123
```

---

## 🔐 Config

### 1. Получить конфигурацию

```bash
curl -X GET http://localhost:8000/api/v1/config/full
```

---

### 2. Системные фразы

```bash
curl -X GET http://localhost:8000/api/v1/config/phrases
```

---

## ✅ Обработка ошибок

### Пример ошибки валидации

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "question",
        "reason": "Cannot be empty"
      },
      {
        "field": "session_id",
        "reason": "Invalid format"
      }
    ],
    "trace_id": "req-abc-123"
  }
}
```

---

## 🛠️ Python Client пример

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def chat_completions(question: str, session_id: str, user_id: str):
    response = requests.post(
        f"{BASE_URL}/chat/completions",
        json={
            "question": question,
            "session_id": session_id,
            "user_id": user_id
        }
    )

    if response.status_code == 200:
        data = response.json()
        return data["data"]["answer"]
    else:
        error = response.json()
        print(f"Error ({error['error']['code']}): {error['error']['message']}")
        return None

def chat_stream(question: str, session_id: str, user_id: str):
    response = requests.post(
        f"{BASE_URL}/chat/stream",
        json={
            "question": question,
            "session_id": session_id,
            "user_id": user_id
        },
        stream=True
    )

    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode().replace('data: ', ''))
            if data.get('token') and data['token'] != '[DONE]':
                print(data['token'], end='', flush=True)

# Использование
answer = chat_completions("Как работает система?", "sess_123", "user_456")
print("\nПотоковый ответ:")
chat_stream("Расскажи подробно", "sess_123", "user_456")
```

---

**Все примеры соответствуют исходному плану из API_RESTRUCTURING_PLAN.md**
