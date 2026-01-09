# План Вебхуков (Webhooks) для Support RAG

**Дата:** 2025-01-09
**Статус:** Детальный план для входящих и исходящих вебхуков
**Интеграция с:** REST API (`/api/v1`)

---

## 📋 Оглавление

1. [Архитектура вебхуков](#архитектура-вебхуков)
2. [Входящие вебхуки (Incoming)](#входящие-вебхуки-incoming)
3. [Исходящие вебхуки (Outgoing)](#исходящие-вебхуки-outgoing)
4. [Управление вебхуками](#управление-вебхуками)
5. [Безопасность](#безопасность)
6. [Retry механизм](#retry-механизм)
7. [Примеры использования](#примеры-использования)
8. [Чек-лист реализации](#чек-лист-реализации)

---

## 🏗️ Архитектура вебхуков

### Общая схема

```
Внешняя система (A)
    ↓ (HTTP POST)
[Входящий вебхук] → Validation → Service Layer → БД/Redis
    ↓
Приложение Support RAG
    ↓
[Исходящий вебхук] → Event → Queue (Redis) → Retry Worker → Внешняя система (B)
    ↓
Внешняя система (B) получает событие
```

### Ключевые компоненты

1. **Webhook Registry** - хранилище зарегистрированных вебхуков (DB)
2. **Webhook Queue** - очередь исходящих вебхуков (Redis)
3. **Webhook Worker** - фоновый рабочий для отправки (async task)
4. **Webhook Validator** - валидация входящих вебхуков (signature verification)
5. **Webhook Logger** - логирование всех попыток (audit trail)

---

## 🔌 Входящие вебхуки (Incoming)

Позволяют внешним системам отправлять нам данные.

### 1. Входящий вебхук: Новое сообщение

**Когда используется:** Когда внешний чат/мессенджер отправляет новое сообщение

**Endpoint:** `POST /api/v1/webhooks/incoming/message`

**Headers (обязательные):**
```
X-Webhook-Signature: sha256=<signature>
X-Webhook-Timestamp: 1641038400
X-Webhook-ID: webhook_123
```

**Request Payload:**
```json
{
  "event_type": "message.received",
  "timestamp": "2025-01-09T12:00:00Z",
  "source": "slack",
  "data": {
    "user_id": "user_slack_123",
    "user_name": "John Doe",
    "message": "Как работает RAG?",
    "thread_id": "thread_abc",
    "channel": "general",
    "external_message_id": "msg_slack_456"
  },
  "metadata": {
    "source_system": "slack",
    "correlation_id": "corr_789"
  }
}
```

**Response (201 Created):**
```json
{
  "data": {
    "webhook_event_id": "evt_123",
    "status": "accepted",
    "message": "Webhook received and queued for processing",
    "session_id": "sess_456"
  },
  "meta": {
    "trace_id": "trace_xyz"
  }
}
```

**Обработка:**
1. Валидировать signature
2. Парсить payload
3. Создать или получить session для пользователя
4. Поместить в очередь обработки
5. Вернуть 202 Accepted
6. Асинхронно: обработать через RAG пайплайн, отправить исходящий вебхук с ответом

---

### 2. Входящий вебхук: Загрузка документов

**Endpoint:** `POST /api/v1/webhooks/incoming/document`

**Request Payload:**
```json
{
  "event_type": "document.upload",
  "timestamp": "2025-01-09T12:00:00Z",
  "source": "external_system",
  "data": {
    "document_url": "https://example.com/docs/guide.pdf",
    "document_name": "User Guide",
    "document_format": "pdf",
    "external_document_id": "doc_ext_123",
    "metadata": {
      "category": "tutorial",
      "author": "System",
      "version": "2.0"
    }
  }
}
```

**Обработка:**
1. Валидировать signature
2. Скачать документ с URL (или получить из формата)
3. Поместить в staging (Redis)
4. Вернуть webhook_event_id
5. Асинхронно: обработать, индексировать, отправить исходящий вебхук с результатом

---

### 3. Входящий вебхук: События от внешних систем

**Endpoint:** `POST /api/v1/webhooks/incoming/event`

**Request Payload:**
```json
{
  "event_type": "custom.event",
  "timestamp": "2025-01-09T12:00:00Z",
  "source": "external_system",
  "data": {
    "event_name": "user_action",
    "user_id": "user_ext_123",
    "action": "viewed_documentation",
    "details": { ... }
  }
}
```

---

## 📤 Исходящие вебхуки (Outgoing)

Система отправляет события внешним системам.

### События, которые отправляются

| Событие | Когда | Payload |
|--------|-------|---------|
| `chat.message.received` | Новое сообщение от пользователя | message, session_id, user_id |
| `chat.response.generated` | Ответ сгенерирован | answer, sources, confidence, session_id |
| `chat.escalated` | Диалог эскалирован на оператора | reason, operator_id, session_id |
| `knowledge.document.uploaded` | Документ загружен | document_id, name, size, staging_id |
| `knowledge.document.indexed` | Документ проиндексирован | document_id, chunks_count, status |
| `knowledge.document.failed` | Ошибка обработки документа | document_id, error, retry_count |
| `analysis.classification.completed` | Классификация завершена | document_id, classifications, timestamp |
| `session.created` | Новая сессия создана | session_id, user_id, timestamp |
| `session.ended` | Сессия завершена | session_id, duration, message_count |
| `error.occurred` | Ошибка в системе | error_code, error_message, severity |

---

### Структура исходящего вебхука

**POST `https://external-system.com/webhooks/support-rag`**

```json
{
  "webhook_id": "webhook_123",
  "event_id": "evt_789",
  "event_type": "chat.response.generated",
  "timestamp": "2025-01-09T12:00:05Z",
  "delivery_attempt": 1,
  "data": {
    "session_id": "sess_456",
    "user_id": "user_789",
    "message": "Как работает RAG?",
    "answer": "RAG (Retrieval-Augmented Generation) - это метод...",
    "sources": [
      {
        "document_id": "doc_123",
        "title": "RAG Guide",
        "excerpt": "..."
      }
    ],
    "confidence": 0.95
  },
  "metadata": {
    "trace_id": "trace_xyz",
    "correlation_id": "corr_abc"
  }
}
```

**Headers (отправляемые):**
```
X-Webhook-Signature: sha256=<signature>
X-Webhook-Timestamp: 1641038405
X-Webhook-ID: webhook_123
X-Delivery-Attempt: 1
X-Event-ID: evt_789
```

**Expected Response (внешняя система):**
```json
{
  "status": "received",
  "message": "Webhook processed successfully"
}
```

**Успешная доставка:** HTTP 2xx
**Ошибка доставки:** HTTP 4xx, 5xx → retry

---

## 🎛️ Управление вебхуками

### 1. Регистрация вебхука

**Endpoint:** `POST /api/v1/webhooks/register`

**Request:**
```json
{
  "name": "My External System",
  "description": "Integration with external CRM",
  "url": "https://external-system.com/webhooks/support-rag",
  "events": [
    "chat.response.generated",
    "chat.escalated",
    "knowledge.document.indexed"
  ],
  "secret": "your_secret_key_for_signing",
  "active": true,
  "metadata": {
    "system": "crm",
    "version": "1.0"
  }
}
```

**Response (201 Created):**
```json
{
  "data": {
    "webhook_id": "webhook_123",
    "name": "My External System",
    "url": "https://external-system.com/webhooks/support-rag",
    "events": ["chat.response.generated", "chat.escalated", "knowledge.document.indexed"],
    "active": true,
    "created_at": "2025-01-09T12:00:00Z",
    "secret_hash": "sha256:..." // для верификации
  },
  "meta": {
    "trace_id": "trace_xyz"
  }
}
```

---

### 2. Список вебхуков

**Endpoint:** `GET /api/v1/webhooks`

**Query Parameters:**
- `active`: bool (фильтр по активности)
- `event`: string (фильтр по событию)
- `limit`: int (default 20)
- `offset`: int (default 0)

**Response:**
```json
{
  "data": [
    {
      "webhook_id": "webhook_123",
      "name": "My External System",
      "url": "https://external-system.com/webhooks/support-rag",
      "events": ["chat.response.generated"],
      "active": true,
      "last_delivery": "2025-01-09T11:50:00Z",
      "deliveries_count": 150,
      "failures_count": 2,
      "created_at": "2025-01-09T10:00:00Z"
    }
  ],
  "meta": {
    "trace_id": "trace_xyz",
    "pagination": {"limit": 20, "offset": 0, "total": 5}
  }
}
```

---

### 3. Получить вебхук

**Endpoint:** `GET /api/v1/webhooks/{webhook_id}`

---

### 4. Обновить вебхук

**Endpoint:** `PATCH /api/v1/webhooks/{webhook_id}`

**Request:**
```json
{
  "url": "https://new-url.com/webhooks",
  "events": ["chat.response.generated", "error.occurred"],
  "active": true
}
```

---

### 5. Удалить вебхук

**Endpoint:** `DELETE /api/v1/webhooks/{webhook_id}`

---

### 6. История доставок

**Endpoint:** `GET /api/v1/webhooks/{webhook_id}/deliveries`

**Response:**
```json
{
  "data": [
    {
      "delivery_id": "dlv_123",
      "event_id": "evt_789",
      "event_type": "chat.response.generated",
      "status": "success",
      "http_status": 200,
      "response_time_ms": 145,
      "attempt": 1,
      "timestamp": "2025-01-09T12:00:05Z",
      "error": null
    },
    {
      "delivery_id": "dlv_124",
      "event_id": "evt_790",
      "event_type": "chat.escalated",
      "status": "failed",
      "http_status": 500,
      "response_time_ms": 5000,
      "attempt": 1,
      "timestamp": "2025-01-09T12:01:05Z",
      "error": "Internal Server Error",
      "next_retry": "2025-01-09T12:05:05Z"
    }
  ],
  "meta": {
    "pagination": {"limit": 20, "offset": 0, "total": 150}
  }
}
```

---

### 7. Повторно отправить вебхук

**Endpoint:** `POST /api/v1/webhooks/deliveries/{delivery_id}/retry`

**Response:**
```json
{
  "data": {
    "delivery_id": "dlv_125",
    "status": "queued",
    "attempt": 2,
    "scheduled_for": "2025-01-09T12:05:05Z"
  },
  "meta": {
    "trace_id": "trace_xyz"
  }
}
```

---

## 🔒 Безопасность

### 1. Signing (HMAC-SHA256)

**Для входящих вебхуков:**

```python
import hmac
import hashlib

def verify_incoming_webhook(request_body: bytes, signature: str, secret: str) -> bool:
    """
    Verify incoming webhook signature

    Header: X-Webhook-Signature: sha256=<signature>
    """
    expected_signature = hmac.new(
        secret.encode(),
        request_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature.split('=')[1], expected_signature)
```

**Для исходящих вебхуков:**

```python
def create_outgoing_webhook_signature(payload: str, secret: str, timestamp: str) -> str:
    """
    Create signature for outgoing webhook

    Message = f"{timestamp}.{payload}"
    """
    message = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    return f"sha256={signature}"
```

**Внешняя система должна:**
1. Получить timestamp из заголовка `X-Webhook-Timestamp`
2. Получить signature из заголовка `X-Webhook-Signature`
3. Воссоздать message = `{timestamp}.{body}`
4. Пересчитать signature = HMAC-SHA256(message, secret)
5. Сравнить с полученной signature

### 2. IP Whitelisting (опционально)

Разрешить вебхуки только с определенных IP адресов:

```json
{
  "webhook_id": "webhook_123",
  "ip_whitelist": [
    "203.0.113.0/24",
    "198.51.100.50"
  ]
}
```

### 3. Rate Limiting

- Макс 1000 вебхуков в час на одного получателя
- Макс 10 одновременных доставок на один webhook

---

## 🔄 Retry механизм

### Exponential Backoff

```
Попытка 1: Немедленно (0 сек)
Попытка 2: 5 сек
Попытка 3: 30 сек (5 * 6)
Попытка 4: 180 сек (30 * 6)
Попытка 5: 900 сек (180 * 5)
Попытка 6: 3600 сек (900 * 4)
Попытка 7: 10800 сек (3600 * 3)
```

**Максимум 7 попыток за 24 часа**

### Когда НЕ повторять

- 400 Bad Request (невалидный payload)
- 401 Unauthorized (неправильный API ключ)
- 403 Forbidden (нет доступа)
- 410 Gone (ресурс не существует)

### Когда повторять

- 408 Request Timeout
- 429 Too Many Requests
- 5xx Server errors
- Timeout (>30 сек)

---

## 📊 Примеры использования

### Сценарий 1: Интеграция с внешним CRM

**Внешняя система:** Salesforce CRM

**Шаг 1: Регистрируем вебхук**

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Salesforce Sync",
    "url": "https://salesforce.example.com/webhooks/support-rag",
    "events": [
      "chat.response.generated",
      "chat.escalated",
      "session.ended"
    ],
    "secret": "my_salesforce_secret_key",
    "active": true,
    "metadata": {
      "crm": "salesforce",
      "org_id": "00D5000000IZ3Z"
    }
  }'
```

**Шаг 2: Система отправляет события в Salesforce**

Когда пользователь получает ответ:
```json
POST https://salesforce.example.com/webhooks/support-rag

Headers:
X-Webhook-Signature: sha256=abc123...
X-Webhook-ID: webhook_123
X-Webhook-Timestamp: 1641038400

Body:
{
  "webhook_id": "webhook_123",
  "event_type": "chat.response.generated",
  "data": {
    "session_id": "sess_456",
    "user_id": "user_789",
    "answer": "...",
    "confidence": 0.95
  }
}
```

**Шаг 3: Salesforce обновляет контакт**

```javascript
// В Salesforce
const delivery = req.body;

if (delivery.event_type === 'chat.response.generated') {
  // Обновить Case в Salesforce
  await updateCase(delivery.data.session_id, {
    Status: 'Awaiting Customer Response',
    LastAIResponse: delivery.data.answer,
    Confidence: delivery.data.confidence
  });
}
```

---

### Сценарий 2: Входящий вебхук из Slack

**Внешняя система:** Slack приложение отправляет сообщения

**Шаг 1: Slack отправляет сообщение**

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/incoming/message \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=xyz..." \
  -H "X-Webhook-ID: slack_webhook_1" \
  -H "X-Webhook-Timestamp: 1641038400" \
  -d '{
    "event_type": "message.received",
    "source": "slack",
    "data": {
      "user_id": "U123456",
      "user_name": "John Doe",
      "message": "Как использовать RAG?",
      "channel": "general",
      "external_message_id": "msg_slack_789"
    }
  }'
```

**Шаг 2: Support RAG обрабатывает и отправляет ответ**

Входящий вебхук возвращает:
```json
{
  "data": {
    "webhook_event_id": "evt_123",
    "status": "accepted",
    "session_id": "sess_456"
  }
}
```

Асинхронно система:
1. Обрабатывает сообщение через RAG пайплайн
2. Генерирует ответ
3. Отправляет исходящий вебхук в Slack приложение:

```json
POST https://slack-app.example.com/webhooks/support-rag

{
  "event_type": "chat.response.generated",
  "data": {
    "session_id": "sess_456",
    "answer": "RAG это метод...",
    "sources": [...],
    "slack_metadata": {
      "channel": "general",
      "external_message_id": "msg_slack_789"
    }
  }
}
```

4. Slack приложение получает ответ и отправляет его в Slack

---

## 📁 Структура БД

### Таблица: webhooks

```sql
CREATE TABLE webhooks (
  webhook_id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  url VARCHAR(2048) NOT NULL,
  events TEXT, -- JSON array of event types
  secret_hash VARCHAR(255) NOT NULL, -- HMAC-SHA256
  active BOOLEAN DEFAULT TRUE,
  ip_whitelist TEXT, -- JSON array of IP/CIDR
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  created_by VARCHAR(255),
  metadata JSON,

  UNIQUE(url),
  INDEX(active),
  INDEX(created_at)
);
```

### Таблица: webhook_deliveries

```sql
CREATE TABLE webhook_deliveries (
  delivery_id VARCHAR(36) PRIMARY KEY,
  webhook_id VARCHAR(36) NOT NULL REFERENCES webhooks(webhook_id),
  event_id VARCHAR(36) NOT NULL,
  event_type VARCHAR(255) NOT NULL,
  payload JSON NOT NULL,
  status VARCHAR(50), -- pending, queued, sent, success, failed
  http_status INT,
  response_body TEXT,
  attempt INT DEFAULT 1,
  max_attempts INT DEFAULT 7,
  next_retry TIMESTAMP,
  error_message TEXT,
  response_time_ms INT,
  created_at TIMESTAMP DEFAULT NOW(),
  delivered_at TIMESTAMP,

  FOREIGN KEY(webhook_id) REFERENCES webhooks(webhook_id),
  INDEX(status),
  INDEX(webhook_id),
  INDEX(created_at),
  INDEX(next_retry)
);
```

---

## 🔧 Чек-лист реализации

### Фаза 1: Управление вебхуками

- [ ] Таблица `webhooks` (CRUD)
- [ ] Таблица `webhook_deliveries` (логирование)
- [ ] Endpoints для регистрации/управления вебхуками
- [ ] Signing/verification функции (HMAC-SHA256)

### Фаза 2: Входящие вебхуки

- [ ] POST /api/v1/webhooks/incoming/message
- [ ] POST /api/v1/webhooks/incoming/document
- [ ] POST /api/v1/webhooks/incoming/event
- [ ] Валидация signature
- [ ] Валидация payload
- [ ] Интеграция с Service Layer

### Фаза 3: Исходящие вебхуки

- [ ] Event publisher (отправка событий в очередь)
- [ ] Webhook queue (Redis)
- [ ] Webhook worker (фоновая задача)
- [ ] Signing для исходящих
- [ ] Retry logic (exponential backoff)
- [ ] Logging и мониторинг

### Фаза 4: Дополнительно

- [ ] IP whitelisting
- [ ] Rate limiting
- [ ] History API
- [ ] Retry API
- [ ] Мониторинг доставок
- [ ] Webhook testing tool

---

## 📊 Матрица событий

| Событие | Тип | Источник | Destination |
|--------|-----|----------|-------------|
| `message.received` | Входящий | Slack, Telegram, etc | Support RAG |
| `document.upload` | Входящий | External system | Support RAG |
| `chat.response.generated` | Исходящий | Support RAG | CRM, Chat system |
| `chat.escalated` | Исходящий | Support RAG | Operator system |
| `knowledge.document.indexed` | Исходящий | Support RAG | External search |
| `error.occurred` | Исходящий | Support RAG | Monitoring system |
| `session.ended` | Исходящий | Support RAG | Analytics |

---

## 🔌 Интеграция с REST API

### Дублирование функционала

Некоторые операции доступны как через REST API, так и через вебхуки:

| Операция | REST API | Webhook |
|----------|----------|---------|
| Отправить сообщение | `POST /chat/completions` | Исходящий `chat.response.generated` |
| Загрузить документ | `POST /knowledge/upload` | Входящий `document.upload` |
| Получить статус | `GET /knowledge/deliveries` | N/A (webhook история) |

**Разница:**
- **REST API**: синхронное получение ответа
- **Webhooks**: асинхронное получение события

**Когда использовать:**
- REST API: интерактивные операции, требующие немедленного ответа
- Webhooks: интеграция с внешними системами, обработка событий

---

## 🧪 Тестирование вебхуков

### Mock веб-сервер для тестирования

```python
from flask import Flask, request, jsonify
import hmac
import hashlib

app = Flask(__name__)

SECRET = "test_secret_key"

@app.route('/webhook', methods=['POST'])
def webhook():
    # Получить signature
    signature = request.headers.get('X-Webhook-Signature')
    timestamp = request.headers.get('X-Webhook-Timestamp')

    # Воссоздать и проверить
    message = f"{timestamp}.{request.get_data(as_text=True)}"
    expected = "sha256=" + hmac.new(
        SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return jsonify({"error": "Invalid signature"}), 401

    # Обработать payload
    data = request.json
    print(f"Received event: {data['event_type']}")

    return jsonify({"status": "received"}), 200

if __name__ == '__main__':
    app.run(port=8001, debug=True)
```

---

## 📈 Мониторинг

### Метрики для отслеживания

```
- webhook.events.total (count)
- webhook.deliveries.success (count)
- webhook.deliveries.failed (count)
- webhook.delivery.latency_ms (histogram)
- webhook.retry.attempts (counter)
- webhook.queue.size (gauge)
```

### Алерты

- Webhook delivery failure rate > 5%
- Webhook queue size > 10000
- Webhook retry attempts > 100 в час

---

**Этот план обеспечивает полную интеграцию Support RAG с внешними системами через надежные и безопасные вебхуки.**
