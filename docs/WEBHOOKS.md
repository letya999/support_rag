# Webhook Events Documentation

Support RAG can send real-time notifications to your system when specific events occur. This allows you to integrate RAG lifecycle events into your own business logic.

## 🚀 Getting Started

### 1. Register a Webhook
You can register a webhook through the API:
```bash
POST /api/v1/webhooks
{
  "name": "My Production Monitor",
  "url": "https://your-api.com/webhooks/support-rag",
  "events": ["chat.response.generated", "knowledge.document.indexed"],
  "secret": "your-secure-secret-key"
}
```

### 2. Verify Signatures
Support RAG signs every webhook payload with an HMAC-SHA256 signature.

**Headers:**
- `X-Webhook-Signature`: `sha256=<hex_hmac>`
- `X-Webhook-Timestamp`: `ISO-8601-Timestamp`
- `X-Webhook-Event`: `event.type`

**Verification Logic (Python Example):**
```python
import hmac
import hashlib

def verify(payload, timestamp, signature, secret):
    # Message is timestamp and payload joined by a dot
    message = f"{timestamp}.{payload}"
    expected_sig = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected_sig}", signature)
```

## 🔔 Event Reference

### `chat.response.generated`
Triggered when the RAG pipeline successfully generates an answer to a user query.

**Payload:**
```json
{
  "session_id": "uuid",
  "user_id": "user-string",
  "answer": "The synthesized answer...",
  "confidence": 0.95,
  "query_id": "internal-id"
}
```

---

### `knowledge.document.uploaded`
Triggered when a document is uploaded to the staging area and initial extraction is complete.

**Payload:**
```json
{
  "document_name": "manual_v1.pdf",
  "staging_id": "draft-uuid",
  "total_pairs": 42
}
```

---

### `knowledge.document.indexed`
Triggered when a staging draft is committed and fully indexed for production search.

---

### `chat.escalated`
Triggered when a session is marked for human escalation (manually or automatically).

---

### `error.occurred`
Triggered when an unhandled exception occurs in the API or pipeline.

**Payload:**
```json
{
  "error": "Error message description",
  "endpoint": "/chat/completions"
}
```

## 🔄 Retry Strategy

If your server returns anything other than a `2xx` status code, Support RAG will log the failure. You can manually retry failed deliveries through the `POST /api/v1/webhooks/deliveries/{id}/retry` endpoint.
