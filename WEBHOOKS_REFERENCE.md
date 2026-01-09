# Webhooks Reference - Краткий справочник

**Базовый URL:** `http://localhost:8000/api/v1`

---

## 📚 Документация

- **[WEBHOOKS_PLAN.md](./WEBHOOKS_PLAN.md)** - Полный детальный план вебхуков
- **[WEBHOOKS_EXAMPLES.md](./WEBHOOKS_EXAMPLES.md)** - Практические примеры
- **[API_REFERENCE.md](./API_REFERENCE.md)** - REST API справочник

---

## 🎯 Входящие вебхуки (Incoming)

**Когда:** Внешние системы отправляют нам данные

```
POST /webhooks/incoming/message      - Новое сообщение (Slack, Telegram, etc)
POST /webhooks/incoming/document     - Загрузка документа
POST /webhooks/incoming/event        - Кастомные события
```

### Headers (обязательные)
```
X-Webhook-Signature: sha256=<hmac>
X-Webhook-Timestamp: <unix timestamp>
X-Webhook-ID: <webhook_id>
```

### Response (202 Accepted)
```json
{
  "data": {
    "webhook_event_id": "evt_123",
    "status": "accepted",
    "session_id": "sess_456"
  },
  "meta": {
    "trace_id": "trace_xyz"
  }
}
```

---

## 📤 Исходящие вебхуки (Outgoing)

**Когда:** Support RAG отправляет события внешним системам

### События

| Событие | Когда | Данные |
|---------|-------|--------|
| `chat.message.received` | Новое сообщение | message, session_id, user_id |
| `chat.response.generated` | Ответ сгенерирован | answer, sources, confidence |
| `chat.escalated` | Эскалация | reason, operator_id, priority |
| `knowledge.document.uploaded` | Документ загружен | document_id, name, size |
| `knowledge.document.indexed` | Документ проиндексирован | document_id, chunks_count |
| `knowledge.document.failed` | Ошибка загрузки | document_id, error, retry_count |
| `analysis.classification.completed` | Классификация готова | document_id, classifications |
| `session.created` | Сессия начата | session_id, user_id |
| `session.ended` | Сессия завершена | session_id, duration, message_count |
| `error.occurred` | Ошибка в системе | error_code, error_message, severity |

---

## 🛠️ Управление вебхуками

### Регистрация

```bash
POST /webhooks/register
{
  "name": "My Integration",
  "url": "https://...",
  "events": ["chat.response.generated"],
  "secret": "secret_key",
  "active": true
}
```

**Response:** `webhook_id`, `created_at`

---

### Список

```bash
GET /webhooks?active=true&limit=20&offset=0
```

**Возвращает:** Массив вебхуков с статистикой (success_rate, failures_count, etc)

---

### Информация

```bash
GET /webhooks/{webhook_id}
```

---

### Обновить

```bash
PATCH /webhooks/{webhook_id}
{
  "url": "https://new-url.com",
  "events": [...],
  "active": true
}
```

---

### Удалить

```bash
DELETE /webhooks/{webhook_id}
```

---

## 📊 История доставок

### Список доставок

```bash
GET /webhooks/{webhook_id}/deliveries?status=failed&limit=20
```

**Возвращает:** Массив доставок с:
- `status`: pending, queued, sent, success, failed
- `http_status`: HTTP код ответа
- `attempt`: Номер попытки
- `error`: Текст ошибки
- `next_retry`: Когда будет следующая попытка

---

### Повторно отправить

```bash
POST /webhooks/deliveries/{delivery_id}/retry
```

**Response:** `status: queued`, `attempt: 2`, `scheduled_for: ...`

---

## 🔒 Безопасность

### Signing (HMAC-SHA256)

**Входящие:**
```python
signature = "sha256=" + hmac(secret, body, sha256).hex()
# Проверить signature == X-Webhook-Signature header
```

**Исходящие:**
```python
message = f"{timestamp}.{json.dumps(payload)}"
signature = "sha256=" + hmac(secret, message, sha256).hex()
# Отправить в X-Webhook-Signature header
```

---

### Timestamp Validation

Проверить что timestamp не старше 5 минут:
```python
import time
webhook_timestamp = int(request.headers['X-Webhook-Timestamp'])
current_time = int(time.time())
if current_time - webhook_timestamp > 300:  # 5 минут
    return 401 Unauthorized
```

---

## 🔄 Retry логика

| Попытка | Delay | Статус |
|---------|-------|--------|
| 1 | 0 сек | немедленно |
| 2 | 5 сек | |
| 3 | 30 сек | |
| 4 | 180 сек | 3 мин |
| 5 | 900 сек | 15 мин |
| 6 | 3600 сек | 1 час |
| 7 | 10800 сек | 3 часа |

**Max 7 попыток за 24 часа**

---

### Не повторять при

- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 410 Gone

---

### Повторять при

- 408 Request Timeout
- 429 Too Many Requests
- 5xx Server errors
- Network timeout (>30 сек)

---

## 📋 Payload структура

### Входящий вебхук

```json
{
  "event_type": "message.received",
  "timestamp": "2025-01-09T12:00:00Z",
  "source": "slack|telegram|external",
  "data": { /* event-specific */ },
  "metadata": { /* custom */ }
}
```

### Исходящий вебхук

```json
{
  "webhook_id": "webhook_123",
  "event_id": "evt_789",
  "event_type": "chat.response.generated",
  "timestamp": "2025-01-09T12:00:05Z",
  "delivery_attempt": 1,
  "data": { /* event data */ },
  "metadata": {
    "trace_id": "...",
    "correlation_id": "..."
  }
}
```

---

## 🎯 Быстрые примеры

### Регистрировать вебхук
```bash
curl -X POST http://localhost:8000/api/v1/webhooks/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My CRM",
    "url": "https://crm.example.com/webhooks",
    "events": ["chat.response.generated"],
    "secret": "secret_key_here",
    "active": true
  }'
```

### Получить список
```bash
curl -X GET "http://localhost:8000/api/v1/webhooks?limit=10"
```

### Получить историю доставок
```bash
curl -X GET "http://localhost:8000/api/v1/webhooks/webhook_123/deliveries"
```

### Повторить доставку
```bash
curl -X POST http://localhost:8000/api/v1/webhooks/deliveries/dlv_123/retry
```

### Отправить входящий вебхук (от внешней системы)
```bash
curl -X POST http://localhost:8000/api/v1/webhooks/incoming/message \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=..." \
  -H "X-Webhook-Timestamp: 1641038400" \
  -H "X-Webhook-ID: webhook_123" \
  -d '{
    "event_type": "message.received",
    "source": "slack",
    "data": { "user_id": "...", "message": "..." }
  }'
```

---

## 🔌 Интеграция с REST API

| Операция | REST API | Webhook |
|----------|----------|---------|
| Получить полный ответ | `POST /chat/completions` | Исходящий `chat.response.generated` |
| Отправить сообщение | Входящий webhook | `chat.message.received` |
| Загрузить документ | `POST /knowledge/upload` | Входящий `document.upload` |
| Статус обработки | Долгополлинг | Исходящие события (`indexed`, `failed`) |

**Выбор:**
- **REST API**: синхронное получение ответа
- **Webhooks**: асинхронное уведомление о событии

---

## 📈 Монитор

### Важные метрики

- `webhook.deliveries.success_rate` - % успешных доставок
- `webhook.queue.size` - размер очереди отправки
- `webhook.delivery.latency_ms` - время доставки
- `webhook.retry.total` - всего повторных попыток

### Алерты

- Success rate < 95%
- Queue size > 10000
- Latency > 5000 ms
- Retry attempts > 100/час

---

## 🧪 Тестирование

### Тестовый вебхук сервер

```bash
# Python Flask
python -c "
from flask import Flask, request
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    print(f'Event: {request.json[\"event_type\"]}')
    return {'status': 'received'}, 200

app.run(port=8001)
"

# Node.js Express
node -e "
const express = require('express');
const app = express();
app.use(express.json());

app.post('/webhook', (req, res) => {
    console.log('Event:', req.body.event_type);
    res.json({status: 'received'});
});

app.listen(8001);
"
```

### ngrok для локального тестирования

```bash
ngrok http 8001
# Используйте выданный URL для регистрации вебхука
```

---

## 📚 Дополнительные документы

- [API_IMPLEMENTATION_PLAN.md](./API_IMPLEMENTATION_PLAN.md) - REST API план
- [API_USAGE_EXAMPLES.md](./API_USAGE_EXAMPLES.md) - REST примеры
- [API_RESTRUCTURING_PLAN.md](./API_RESTRUCTURING_PLAN.md) - Исходный план

---

**Все примеры и структуры соответствуют WEBHOOKS_PLAN.md**
