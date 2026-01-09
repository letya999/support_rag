# Примеры использования Webhooks

**Основано на:** [WEBHOOKS_PLAN.md](./WEBHOOKS_PLAN.md)
**Базовый URL:** `http://localhost:8000/api/v1`

---

## 📋 Быстрый старт

### 1. Зарегистрировать вебхук

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Integration",
    "url": "https://my-system.example.com/webhooks",
    "events": [
      "chat.response.generated",
      "chat.escalated",
      "knowledge.document.indexed"
    ],
    "secret": "my_secret_key_12345",
    "active": true
  }'
```

**Ответ:**
```json
{
  "data": {
    "webhook_id": "webhook_abc123",
    "name": "My Integration",
    "url": "https://my-system.example.com/webhooks",
    "events": ["chat.response.generated", "chat.escalated", "knowledge.document.indexed"],
    "active": true,
    "created_at": "2025-01-09T12:00:00Z"
  },
  "meta": {
    "trace_id": "trace_xyz"
  }
}
```

---

## 🔌 Входящие вебхуки

### Пример 1: Сообщение из Slack

**Slack приложение отправляет:**

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/incoming/message \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=b95e2a0b0f3e8e1b4f5c6d7e8f9a0b1c2d3e4f5" \
  -H "X-Webhook-Timestamp: 1641038400" \
  -H "X-Webhook-ID: webhook_slack_123" \
  -d '{
    "event_type": "message.received",
    "timestamp": "2025-01-09T12:00:00Z",
    "source": "slack",
    "data": {
      "user_id": "U123456789",
      "user_name": "John Doe",
      "message": "Как работает документирование?",
      "thread_id": "1234567890.123456",
      "channel": "support",
      "external_message_id": "1234567890.123456"
    },
    "metadata": {
      "workspace": "myworkspace",
      "correlation_id": "corr_abc123"
    }
  }'
```

**Support RAG ответ:**
```json
{
  "data": {
    "webhook_event_id": "evt_incoming_123",
    "status": "accepted",
    "session_id": "sess_slack_456",
    "message": "Сообщение принято и поставлено в очередь обработки"
  },
  "meta": {
    "trace_id": "trace_req_123"
  }
}
```

**Асинхронная обработка:**
1. Support RAG обрабатывает сообщение через RAG пайплайн
2. Генерирует ответ
3. Отправляет исходящий вебхук в Slack приложение

---

### Пример 2: Загрузка документа из внешней системы

**Внешняя система отправляет:**

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/incoming/document \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=..." \
  -H "X-Webhook-Timestamp: 1641038400" \
  -H "X-Webhook-ID: webhook_ext_doc" \
  -d '{
    "event_type": "document.upload",
    "timestamp": "2025-01-09T12:00:00Z",
    "source": "knowledge_management_system",
    "data": {
      "document_url": "https://company.example.com/docs/policy-2025.pdf",
      "document_name": "Company Policy 2025",
      "document_format": "pdf",
      "external_document_id": "doc_ext_policy_001",
      "metadata": {
        "category": "policies",
        "department": "HR",
        "version": "2.1",
        "author": "HR Department",
        "effective_date": "2025-01-01"
      }
    }
  }'
```

**Ответ:**
```json
{
  "data": {
    "webhook_event_id": "evt_doc_123",
    "status": "accepted",
    "message": "Документ принят на загрузку",
    "staging_id": "staging_456"
  },
  "meta": {
    "trace_id": "trace_doc_123"
  }
}
```

---

## 📤 Исходящие вебхуки

### Пример 1: Ответ на сообщение

**Когда:** Пользователь получил ответ от RAG

**Support RAG отправляет на:**
```
https://my-system.example.com/webhooks
```

**Payload:**
```json
{
  "webhook_id": "webhook_abc123",
  "event_id": "evt_chat_response_789",
  "event_type": "chat.response.generated",
  "timestamp": "2025-01-09T12:00:05Z",
  "delivery_attempt": 1,
  "data": {
    "session_id": "sess_slack_456",
    "user_id": "user_slack_123",
    "message": "Как работает документирование?",
    "answer": "Документирование в нашей системе работает следующим образом: мы используем RAG (Retrieval-Augmented Generation) для поиска релевантных документов и генерации ответов на основе контекста...",
    "sources": [
      {
        "document_id": "doc_123",
        "title": "Documentation Guide",
        "excerpt": "RAG combines retrieval and generation..."
      },
      {
        "document_id": "doc_456",
        "title": "System Architecture",
        "excerpt": "The documentation system is built on..."
      }
    ],
    "confidence": 0.94,
    "processing_time_ms": 1245
  },
  "metadata": {
    "trace_id": "trace_req_123",
    "correlation_id": "corr_abc123"
  }
}
```

**Headers:**
```
POST /webhooks HTTP/1.1
Host: my-system.example.com
Content-Type: application/json
Content-Length: 2348
X-Webhook-Signature: sha256=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
X-Webhook-Timestamp: 1641038405
X-Webhook-ID: webhook_abc123
X-Delivery-Attempt: 1
X-Event-ID: evt_chat_response_789
User-Agent: SupportRAG/1.0
```

**Внешняя система должна ответить:**
```json
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "received",
  "message": "Webhook processed successfully",
  "external_reference": "case_slack_789"
}
```

---

### Пример 2: Эскалация диалога

**Когда:** Диалог эскалирован на оператора

**Payload:**
```json
{
  "webhook_id": "webhook_abc123",
  "event_id": "evt_escalation_234",
  "event_type": "chat.escalated",
  "timestamp": "2025-01-09T12:05:00Z",
  "delivery_attempt": 1,
  "data": {
    "session_id": "sess_slack_456",
    "user_id": "user_slack_123",
    "escalation_reason": "Пользователь не доволен ответом AI, требуется помощь оператора",
    "escalation_priority": "high",
    "assigned_operator_id": "op_123",
    "assigned_operator_name": "Jane Smith",
    "conversation_summary": "Пользователь спрашивал о документировании, получил ответ с 94% уверенностью, но требует дополнительного обсуждения...",
    "last_message": "Это не совсем то, что мне нужно. Нужна помощь оператора."
  }
}
```

---

### Пример 3: Документ проиндексирован

**Когда:** Документ успешно загружен, обработан и добавлен в индекс

**Payload:**
```json
{
  "webhook_id": "webhook_abc123",
  "event_id": "evt_doc_indexed_567",
  "event_type": "knowledge.document.indexed",
  "timestamp": "2025-01-09T12:10:00Z",
  "delivery_attempt": 1,
  "data": {
    "document_id": "doc_prod_123",
    "name": "Company Policy 2025",
    "external_document_id": "doc_ext_policy_001",
    "status": "indexed",
    "chunks_count": 42,
    "total_size_bytes": 2097152,
    "processing_time_ms": 5234,
    "metadata": {
      "category": "policies",
      "department": "HR",
      "version": "2.1"
    },
    "embeddings_model": "openai:text-embedding-3-small",
    "vector_store": "qdrant"
  }
}
```

---

### Пример 4: Ошибка обработки документа

**Когда:** Произошла ошибка при обработке документа

**Payload:**
```json
{
  "webhook_id": "webhook_abc123",
  "event_id": "evt_doc_error_890",
  "event_type": "knowledge.document.failed",
  "timestamp": "2025-01-09T12:15:00Z",
  "delivery_attempt": 1,
  "data": {
    "document_id": "doc_failed_123",
    "name": "Corrupted Document",
    "external_document_id": "doc_ext_corrupted_001",
    "status": "failed",
    "error_code": "INVALID_PDF_FORMAT",
    "error_message": "PDF файл повреждён или защищён паролем",
    "retry_count": 1,
    "max_retries": 3,
    "next_retry": "2025-01-09T12:20:00Z"
  }
}
```

---

### Пример 5: Классификация завершена

**Когда:** Документ автоматически классифицирован

**Payload:**
```json
{
  "webhook_id": "webhook_abc123",
  "event_id": "evt_classify_345",
  "event_type": "analysis.classification.completed",
  "timestamp": "2025-01-09T12:25:00Z",
  "data": {
    "document_id": "doc_123",
    "classifications": [
      {
        "intent": "technical_documentation",
        "confidence": 0.96,
        "category": "software"
      },
      {
        "intent": "api_reference",
        "confidence": 0.88,
        "category": "technical"
      }
    ],
    "processing_time_ms": 3456
  }
}
```

---

## 🛠️ Управление вебхуками

### Получить список вебхуков

```bash
curl -X GET "http://localhost:8000/api/v1/webhooks?active=true&limit=10" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "data": [
    {
      "webhook_id": "webhook_abc123",
      "name": "My Integration",
      "url": "https://my-system.example.com/webhooks",
      "events": ["chat.response.generated", "chat.escalated"],
      "active": true,
      "last_delivery": "2025-01-09T12:00:05Z",
      "deliveries_count": 150,
      "failures_count": 2,
      "success_rate": 98.67,
      "created_at": "2025-01-09T10:00:00Z"
    }
  ],
  "meta": {
    "trace_id": "trace_xyz",
    "pagination": {
      "limit": 10,
      "offset": 0,
      "total": 5
    }
  }
}
```

---

### Получить информацию о вебхуке

```bash
curl -X GET http://localhost:8000/api/v1/webhooks/webhook_abc123 \
  -H "Content-Type: application/json"
```

---

### Обновить вебхук

```bash
curl -X PATCH http://localhost:8000/api/v1/webhooks/webhook_abc123 \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://new-url.example.com/webhooks",
    "events": [
      "chat.response.generated",
      "chat.escalated",
      "knowledge.document.indexed",
      "error.occurred"
    ],
    "active": true
  }'
```

---

### Получить историю доставок

```bash
curl -X GET "http://localhost:8000/api/v1/webhooks/webhook_abc123/deliveries?status=failed&limit=20" \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "data": [
    {
      "delivery_id": "dlv_123",
      "event_id": "evt_789",
      "event_type": "chat.response.generated",
      "status": "failed",
      "http_status": 500,
      "response_time_ms": 30000,
      "attempt": 1,
      "error": "Internal Server Error - Database timeout",
      "next_retry": "2025-01-09T12:05:00Z",
      "timestamp": "2025-01-09T12:00:00Z"
    },
    {
      "delivery_id": "dlv_124",
      "event_id": "evt_790",
      "event_type": "chat.escalated",
      "status": "success",
      "http_status": 200,
      "response_time_ms": 145,
      "attempt": 1,
      "timestamp": "2025-01-09T12:01:00Z"
    }
  ],
  "meta": {
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 15
    }
  }
}
```

---

### Повторно отправить вебхук

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/deliveries/dlv_123/retry \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "data": {
    "delivery_id": "dlv_123_retry_1",
    "original_delivery_id": "dlv_123",
    "status": "queued",
    "attempt": 2,
    "scheduled_for": "2025-01-09T12:05:00Z"
  },
  "meta": {
    "trace_id": "trace_xyz"
  }
}
```

---

### Удалить вебхук

```bash
curl -X DELETE http://localhost:8000/api/v1/webhooks/webhook_abc123 \
  -H "Content-Type: application/json"
```

**Ответ:**
```json
{
  "data": {
    "webhook_id": "webhook_abc123",
    "status": "deleted",
    "message": "Webhook deleted successfully"
  },
  "meta": {
    "trace_id": "trace_xyz"
  }
}
```

---

## 🔐 Верификация входящего вебхука (Python)

```python
import hmac
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

WEBHOOKS = {
    "slack_webhook_123": "slack_secret_key_12345",
    "external_sys_456": "external_secret_key_67890"
}

def verify_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify incoming webhook signature"""
    expected = "sha256=" + hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature.split('=')[1], expected)

@app.route('/incoming-webhooks/message', methods=['POST'])
def incoming_message_webhook():
    # Получить headers
    signature = request.headers.get('X-Webhook-Signature')
    timestamp = request.headers.get('X-Webhook-Timestamp')
    webhook_id = request.headers.get('X-Webhook-ID')

    # Валидировать
    if webhook_id not in WEBHOOKS:
        return jsonify({"error": "Unknown webhook"}), 401

    secret = WEBHOOKS[webhook_id]
    body = request.get_data()

    if not verify_webhook_signature(body, signature, secret):
        return jsonify({"error": "Invalid signature"}), 401

    # Получить payload
    data = request.json

    # Обработать (асинхронно)
    print(f"Processing message from {data['data']['user_name']}")
    print(f"Message: {data['data']['message']}")

    return jsonify({
        "webhook_event_id": "evt_123",
        "status": "accepted",
        "session_id": "sess_456"
    }), 202

if __name__ == '__main__':
    app.run(port=8001)
```

---

## 🔐 Верификация исходящего вебхука (JavaScript)

```javascript
const crypto = require('crypto');
const express = require('express');

const app = express();
app.use(express.json());

const WEBHOOK_SECRETS = {
    "webhook_abc123": "my_secret_key_12345"
};

function verifyWebhookSignature(payload, signature, timestamp, secret) {
    // Reconstruct message
    const message = `${timestamp}.${JSON.stringify(payload)}`;

    // Calculate expected signature
    const expected = "sha256=" + crypto
        .createHmac('sha256', secret)
        .update(message)
        .digest('hex');

    // Compare
    return crypto.timingSafeEqual(
        Buffer.from(signature),
        Buffer.from(expected)
    );
}

app.post('/webhooks', (req, res) => {
    const signature = req.headers['x-webhook-signature'];
    const timestamp = req.headers['x-webhook-timestamp'];
    const webhookId = req.headers['x-webhook-id'];
    const payload = req.body;

    // Validate webhook exists
    if (!WEBHOOK_SECRETS[webhookId]) {
        return res.status(401).json({ error: "Unknown webhook" });
    }

    // Verify signature
    try {
        const isValid = verifyWebhookSignature(
            payload,
            signature,
            timestamp,
            WEBHOOK_SECRETS[webhookId]
        );

        if (!isValid) {
            return res.status(401).json({ error: "Invalid signature" });
        }
    } catch (err) {
        return res.status(401).json({ error: "Signature verification failed" });
    }

    // Process webhook
    console.log(`Event: ${payload.event_type}`);
    console.log(`Data:`, payload.data);

    res.status(200).json({
        status: "received",
        message: "Webhook processed successfully"
    });
});

app.listen(3000, () => {
    console.log('Webhook receiver listening on port 3000');
});
```

---

## 📊 Реальный сценарий: CRM интеграция

### Шаг 1: Регистрация вебхука в Support RAG

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Salesforce Sync",
    "url": "https://salesforce-webhook-receiver.heroku.com/webhooks",
    "events": [
      "chat.response.generated",
      "chat.escalated",
      "session.ended"
    ],
    "secret": "salesforce_webhook_secret_key",
    "metadata": {
      "crm": "salesforce",
      "org_id": "00D5000000IZ3Z",
      "environment": "production"
    }
  }'
```

### Шаг 2: Пользователь задает вопрос

Приложение отправляет в Support RAG:
```
POST /api/v1/chat/completions
{
  "question": "Как вернуть товар?",
  "session_id": "sess_sf_123",
  "user_id": "user_sf_456"
}
```

### Шаг 3: Support RAG отправляет исходящий вебхук

```json
POST https://salesforce-webhook-receiver.heroku.com/webhooks

{
  "webhook_id": "webhook_sf_123",
  "event_type": "chat.response.generated",
  "data": {
    "session_id": "sess_sf_123",
    "user_id": "user_sf_456",
    "answer": "Для возврата товара...",
    "confidence": 0.92,
    "sources": [...]
  }
}
```

### Шаг 4: Salesforce обновляет кейс

```apex
// В Salesforce webhook receiver
public class SupportRAGWebhookHandler {
    public static void handleResponse(SupportRAGEvent event) {
        Case caseRecord = [
            SELECT Id FROM Case
            WHERE ExternalId = :event.data.session_id
        ];

        caseRecord.Status = 'Awaiting Customer Response';
        caseRecord.AI_Response__c = event.data.answer;
        caseRecord.AI_Confidence__c = event.data.confidence;

        update caseRecord;

        // Отправить ответ пользователю
        sendEmailWithAnswer(caseRecord, event.data.answer);
    }
}
```

---

**Все примеры соответствуют WEBHOOKS_PLAN.md**
