# Примеры использования и данные

## 1. Входные данные (qa.json)

### Пример 1: Простой QA файл (без метаданных)

```json
[
  {
    "question": "How do I reset my password?",
    "answer": "You can reset your password by clicking on the 'Forgot Password' link on the login page. Enter your email address and follow the instructions sent to your inbox."
  },
  {
    "question": "Where can I find my order history?",
    "answer": "Your order history is located in the 'My Account' section. Click on 'Orders' to view all your past purchases and their status."
  },
  {
    "question": "How do I contact support?",
    "answer": "You can contact support via email at support@example.com or by calling 1-800-123-4567. Our support team is available Monday-Friday, 9 AM - 5 PM EST."
  },
  {
    "question": "What is the return policy?",
    "answer": "We accept returns within 30 days of purchase. Items must be in original condition with original packaging. Refunds are processed within 5-7 business days."
  },
  {
    "question": "Can I change my shipping address?",
    "answer": "Yes, you can update your shipping address in your profile settings before an order is shipped. Once shipped, contact our support team to arrange a change."
  },
  {
    "question": "Do you offer international shipping?",
    "answer": "Yes, we ship to most countries worldwide. Shipping costs and delivery times vary by location. Check our shipping policy page for details."
  },
  {
    "question": "How do I track my package?",
    "answer": "A tracking link will be sent to your email once your order has been shipped. You can also track it from the 'My Orders' section in your account."
  },
  {
    "question": "What payment methods do you accept?",
    "answer": "We accept Visa, MasterCard, American Express, PayPal, and Apple Pay. All transactions are secured with SSL encryption."
  },
  {
    "question": "Can I cancel my subscription?",
    "answer": "Yes, you can cancel your subscription at any time from your account settings. Click on 'Subscription' and select 'Cancel Subscription'."
  },
  {
    "question": "Where is the company located?",
    "answer": "Our headquarters are located in San Francisco, CA. We have additional offices in New York and London."
  }
]
```

---

## 2. Выходные данные (после анализа)

### POST /documents/metadata-generation/analyze - Response

```json
{
  "status": "success",
  "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
  "proposed_structure": {
    "categories": [
      {
        "id": "cat_0",
        "name": "Account Management",
        "description": "User account access, password reset, profile management",
        "suggested_intents": [
          "reset_password",
          "account_recovery",
          "profile_update"
        ]
      },
      {
        "id": "cat_1",
        "name": "Order Management",
        "description": "Order tracking, order history, order status",
        "suggested_intents": [
          "track_order",
          "view_order_history",
          "modify_order"
        ]
      },
      {
        "id": "cat_2",
        "name": "Returns & Refunds",
        "description": "Return policy, refund process, return authorization",
        "suggested_intents": [
          "return_item",
          "request_refund",
          "return_status"
        ]
      },
      {
        "id": "cat_3",
        "name": "Shipping & Delivery",
        "description": "Shipping options, delivery times, address changes",
        "suggested_intents": [
          "change_address",
          "check_shipping_options",
          "shipping_cost"
        ]
      },
      {
        "id": "cat_4",
        "name": "Payment Methods",
        "description": "Accepted payment methods, billing, payment issues",
        "suggested_intents": [
          "accepted_payment_methods",
          "payment_issue",
          "update_payment"
        ]
      },
      {
        "id": "cat_5",
        "name": "Support & Contact",
        "description": "Customer support, contact information, help",
        "suggested_intents": [
          "contact_support",
          "technical_support",
          "escalate_issue"
        ]
      },
      {
        "id": "cat_6",
        "name": "International Shipping",
        "description": "International delivery, cross-border shipping",
        "suggested_intents": [
          "international_shipping",
          "customs_info",
          "delivery_time"
        ]
      },
      {
        "id": "cat_7",
        "name": "Subscriptions",
        "description": "Subscription management, cancellation, billing",
        "suggested_intents": [
          "cancel_subscription",
          "modify_subscription",
          "pause_subscription"
        ]
      },
      {
        "id": "cat_8",
        "name": "Company Information",
        "description": "Company details, locations, contact info",
        "suggested_intents": [
          "company_location",
          "company_info",
          "office_locations"
        ]
      },
      {
        "id": "cat_9",
        "name": "General FAQ",
        "description": "Frequently asked questions, general information",
        "suggested_intents": [
          "general_question",
          "faq_search",
          "product_info"
        ]
      },
      {
        "id": "cat_10",
        "name": "Security & Privacy",
        "description": "Data privacy, security, SSL encryption",
        "suggested_intents": [
          "privacy_question",
          "security_issue",
          "data_protection"
        ]
      },
      {
        "id": "cat_11",
        "name": "Billing & Invoices",
        "description": "Billing information, invoices, billing disputes",
        "suggested_intents": [
          "billing_question",
          "invoice_request",
          "billing_issue"
        ]
      },
      {
        "id": "cat_12",
        "name": "Product Catalog",
        "description": "Product information, availability, specifications",
        "suggested_intents": [
          "product_availability",
          "product_specs",
          "product_search"
        ]
      },
      {
        "id": "cat_13",
        "name": "Promotions & Discounts",
        "description": "Discount codes, promotions, special offers",
        "suggested_intents": [
          "apply_coupon",
          "promotion_info",
          "discount_code"
        ]
      },
      {
        "id": "cat_14",
        "name": "Technical Issues",
        "description": "Website errors, app issues, technical problems",
        "suggested_intents": [
          "website_error",
          "app_issue",
          "technical_help"
        ]
      }
    ],
    "qa_pairs": [
      {
        "id": 0,
        "question": "How do I reset my password?",
        "answer": "You can reset your password by clicking on the 'Forgot Password' link on the login page...",
        "suggested_category": "Account Management",
        "suggested_intent": "reset_password",
        "suggested_requires_handoff": false,
        "confidence": {
          "category": 0.96,
          "intent": 0.94,
          "handoff": 0.99
        }
      },
      {
        "id": 1,
        "question": "Where can I find my order history?",
        "answer": "Your order history is located in the 'My Account' section...",
        "suggested_category": "Order Management",
        "suggested_intent": "view_order_history",
        "suggested_requires_handoff": false,
        "confidence": {
          "category": 0.92,
          "intent": 0.88,
          "handoff": 0.98
        }
      },
      {
        "id": 2,
        "question": "How do I contact support?",
        "answer": "You can contact support via email at support@example.com...",
        "suggested_category": "Support & Contact",
        "suggested_intent": "contact_support",
        "suggested_requires_handoff": true,
        "confidence": {
          "category": 0.98,
          "intent": 0.95,
          "handoff": 0.95
        }
      },
      {
        "id": 3,
        "question": "What is the return policy?",
        "answer": "We accept returns within 30 days of purchase...",
        "suggested_category": "Returns & Refunds",
        "suggested_intent": "return_item",
        "suggested_requires_handoff": false,
        "confidence": {
          "category": 0.94,
          "intent": 0.91,
          "handoff": 0.97
        }
      },
      {
        "id": 4,
        "question": "Can I change my shipping address?",
        "answer": "Yes, you can update your shipping address in your profile settings...",
        "suggested_category": "Shipping & Delivery",
        "suggested_intent": "change_address",
        "suggested_requires_handoff": false,
        "confidence": {
          "category": 0.90,
          "intent": 0.87,
          "handoff": 0.96
        }
      },
      {
        "id": 5,
        "question": "Do you offer international shipping?",
        "answer": "Yes, we ship to most countries worldwide...",
        "suggested_category": "International Shipping",
        "suggested_intent": "international_shipping",
        "suggested_requires_handoff": false,
        "confidence": {
          "category": 0.88,
          "intent": 0.85,
          "handoff": 0.99
        }
      },
      {
        "id": 6,
        "question": "How do I track my package?",
        "answer": "A tracking link will be sent to your email...",
        "suggested_category": "Order Management",
        "suggested_intent": "track_order",
        "suggested_requires_handoff": false,
        "confidence": {
          "category": 0.93,
          "intent": 0.90,
          "handoff": 0.98
        }
      },
      {
        "id": 7,
        "question": "What payment methods do you accept?",
        "answer": "We accept Visa, MasterCard, American Express, PayPal, and Apple Pay...",
        "suggested_category": "Payment Methods",
        "suggested_intent": "accepted_payment_methods",
        "suggested_requires_handoff": false,
        "confidence": {
          "category": 0.91,
          "intent": 0.89,
          "handoff": 0.99
        }
      },
      {
        "id": 8,
        "question": "Can I cancel my subscription?",
        "answer": "Yes, you can cancel your subscription at any time...",
        "suggested_category": "Subscriptions",
        "suggested_intent": "cancel_subscription",
        "suggested_requires_handoff": false,
        "confidence": {
          "category": 0.92,
          "intent": 0.90,
          "handoff": 0.97
        }
      },
      {
        "id": 9,
        "question": "Where is the company located?",
        "answer": "Our headquarters are located in San Francisco, CA...",
        "suggested_category": "Company Information",
        "suggested_intent": "company_location",
        "suggested_requires_handoff": false,
        "confidence": {
          "category": 0.89,
          "intent": 0.86,
          "handoff": 0.99
        }
      }
    ],
    "statistics": {
      "total_pairs": 10,
      "total_categories": 15,
      "total_intents": 45,
      "avg_category_confidence": 0.914,
      "avg_intent_confidence": 0.895,
      "avg_handoff_confidence": 0.978,
      "requires_handoff_count": 1,
      "confidence_distribution": {
        "0.9_1.0": 8,
        "0.8_0.9": 2,
        "0.7_0.8": 0,
        "below_0.7": 0
      }
    }
  }
}
```

---

## 3. User Review & Correction Flow

### User sees in UI and makes corrections

```json
{
  "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
  "proposed_corrections": [
    {
      "qa_index": 5,
      "original_category": "International Shipping",
      "original_intent": "international_shipping",
      "corrected_category": "Shipping & Delivery",
      "corrected_intent": "check_shipping_options",
      "reason": "This question applies to domestic users too"
    }
  ],
  "category_renames": [
    {
      "original_name": "General FAQ",
      "new_name": "General Questions"
    },
    {
      "original_name": "International Shipping",
      "new_name": "Global Shipping"
    }
  ],
  "intents_to_merge": [
    {
      "category": "Support & Contact",
      "intent_a": "technical_support",
      "intent_b": "escalate_issue",
      "merged_intent_name": "technical_escalation"
    }
  ],
  "remove_empty_categories": true
}
```

### POST /documents/metadata-generation/review - Response

```json
{
  "status": "review_accepted",
  "validated": true,
  "warnings": [
    "Category 'Promotions & Discounts' has no Q&A pairs assigned"
  ],
  "conflicts": [],
  "summary": {
    "total_corrections": 1,
    "category_renames": 2,
    "merged_intents": 1,
    "categories_removed": 1,
    "final_category_count": 14,
    "final_intent_count": 44
  },
  "ready_for_ingestion": true,
  "updated_structure": {
    "categories": [
      {
        "id": "cat_0",
        "name": "Account Management",
        "intents": ["reset_password", "account_recovery", "profile_update"]
      },
      {
        "id": "cat_1",
        "name": "Order Management",
        "intents": ["track_order", "view_order_history", "modify_order", "check_shipping_options"]
      }
    ]
  }
}
```

---

## 4. Confirmation & Ingestion

### POST /documents/metadata-generation/confirm - Response

```json
{
  "status": "success",
  "ingested_count": 10,
  "registry_updated": true,
  "classifier_refreshed": true,
  "message": "Successfully ingested 10 Q&A pairs with metadata",
  "details": {
    "database_records_created": 10,
    "categories_in_registry": 14,
    "intents_in_registry": 44,
    "registry_file": "app/nodes/_shared_config/intents_registry.yaml",
    "timestamp": "2026-01-06T10:30:45.123456+00:00"
  }
}
```

### Updated intents_registry.yaml

```yaml
# ============================================================
# Intent Registry - AUTO-GENERATED FILE
# ============================================================

_meta:
  generated_at: '2026-01-06T10:30:45.123456+00:00'
  source_db: postgres:documents
  total_categories: 14
  total_intents: 44
  warning: ⚠️ АВТОГЕНЕРИРУЕМЫЙ ФАЙЛ - не редактируйте вручную!

categories:
- name: Account Management
  description: User account access, password reset, profile management
  intents:
  - reset_password
  - account_recovery
  - profile_update

- name: Order Management
  description: Order tracking, order history, order status
  intents:
  - track_order
  - view_order_history
  - modify_order
  - check_shipping_options

- name: Returns & Refunds
  description: Return policy, refund process, return authorization
  intents:
  - return_item
  - request_refund
  - return_status

- name: Shipping & Delivery
  description: Shipping options, delivery times, address changes
  intents:
  - change_address
  - shipping_cost
  - address_verification

- name: Payment Methods
  description: Accepted payment methods, billing, payment issues
  intents:
  - accepted_payment_methods
  - payment_issue
  - update_payment

- name: Support & Contact
  description: Customer support, contact information, help
  intents:
  - contact_support
  - technical_escalation
  - general_inquiry

- name: Global Shipping
  description: International delivery, cross-border shipping
  intents:
  - international_shipping
  - customs_info
  - delivery_time

- name: Subscriptions
  description: Subscription management, cancellation, billing
  intents:
  - cancel_subscription
  - modify_subscription
  - pause_subscription

- name: Company Information
  description: Company details, locations, contact info
  intents:
  - company_location
  - company_info
  - office_locations

- name: General Questions
  description: Frequently asked questions, general information
  intents:
  - general_question
  - faq_search
  - product_info

- name: Security & Privacy
  description: Data privacy, security, SSL encryption
  intents:
  - privacy_question
  - security_issue
  - data_protection

- name: Billing & Invoices
  description: Billing information, invoices, billing disputes
  intents:
  - billing_question
  - invoice_request
  - billing_issue

- name: Product Catalog
  description: Product information, availability, specifications
  intents:
  - product_availability
  - product_specs
  - product_search

- name: Technical Issues
  description: Website errors, app issues, technical problems
  intents:
  - website_error
  - app_issue
  - technical_help
```

---

## 5. Configuration Files

### config/metadata_generation.yaml

```yaml
metadata_generation:
  # Clustering Algorithm Settings
  clustering:
    algorithm: "kmeans"              # Options: "kmeans", "hierarchical", "dbscan"
    random_state: 42                 # For reproducibility
    n_init: 10                       # Number of time k-means will run
    max_iter: 300                    # Maximum iterations for k-means
    init_method: "k-means++"         # Initialization method
    verbose: 0                       # Verbosity level

  # Default Parameters
  defaults:
    num_categories: 15               # Default number of categories
    num_intents_per_category: 3      # Default intents per category
    min_confidence_threshold: 0.6    # Minimum confidence for acceptance
    language: "en"                   # Default language
    batch_size: 32                   # Batch size for embedding

  # Handoff Detection Settings
  handoff_detection:
    use_rules: true                  # Enable rule-based detection
    use_llm: true                    # Enable LLM-based detection
    rule_threshold: 0.7              # Confidence threshold for rules
    llm_threshold: 0.6               # Below this, use LLM for verification
    llm_model: "gpt-4-turbo"         # LLM model for detection
    timeout_seconds: 10              # LLM call timeout

  # Caching Settings
  cache:
    backend: "redis"                 # Options: "redis", "memory"
    ttl_seconds: 3600               # Time to live for cached analysis
    prefix: "metadata_analysis:"     # Redis key prefix
    max_analyses: 1000              # Max concurrent analyses in memory

  # Embedding Settings
  embeddings:
    model: "all-MiniLM-L6-v2"        # SentenceTransformer model
    batch_size: 32                   # Batch size for encoding
    normalize: true                  # Normalize embeddings
    cache_embeddings: true           # Cache computed embeddings

  # LLM Settings for Naming
  llm_naming:
    model: "gpt-4-turbo"
    temperature: 0.7                 # Creativity level
    max_tokens: 100                  # Max tokens for names
    timeout_seconds: 15
    retry_attempts: 3

  # Enrichment Data
  enrichment:
    auto_generate: true              # Auto-generate descriptions
    language: "en"                   # Language for descriptions
    use_semantic_similarity: true    # Use embeddings for matching

  # Validation Settings
  validation:
    check_duplicates: true           # Check for duplicate intents
    check_hierarchy: true            # Verify category-intent hierarchy
    min_category_size: 1             # Minimum Q&A pairs per category
    max_category_size: null          # No maximum

  # API Settings
  api:
    max_file_size_mb: 10             # Max JSON file size
    timeout_minutes: 10              # Analysis timeout
    max_concurrent_analyses: 5       # Max parallel analyses
    cors_enabled: true               # CORS support

  # Logging & Monitoring
  monitoring:
    log_level: "INFO"
    trace_to_langfuse: true
    save_analysis_logs: true         # Save detailed logs
    log_retention_days: 30
```

### .env.example (extensions)

```bash
# ... existing settings ...

# Metadata Generation
METADATA_GEN_CACHE_TTL=3600
METADATA_GEN_DEFAULT_CATEGORIES=15
METADATA_GEN_DEFAULT_INTENTS=3
METADATA_GEN_USE_RULES=true
METADATA_GEN_USE_LLM=true
```

---

## 6. Database Schema Changes

### Migration: Add metadata fields to documents table

```sql
-- This would be auto-generated by SQLAlchemy migration

ALTER TABLE documents ADD COLUMN metadata JSONB DEFAULT '{}';

-- If metadata column doesn't exist yet
-- Add category and intent as top-level fields
ALTER TABLE documents
ADD COLUMN category VARCHAR(255),
ADD COLUMN intent VARCHAR(255),
ADD COLUMN requires_handoff BOOLEAN DEFAULT false,
ADD COLUMN generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Create indexes for faster queries
CREATE INDEX idx_documents_category ON documents(category);
CREATE INDEX idx_documents_intent ON documents(intent);
CREATE INDEX idx_documents_requires_handoff ON documents(requires_handoff);
```

---

## 7. Monitoring & Metrics (Langfuse)

### Metrics to track

```python
# Example of metrics that should be logged to Langfuse

metrics = {
    "metadata_generation": {
        "total_duration_ms": 1234,
        "clustering_duration_ms": 456,
        "classification_duration_ms": 234,
        "embedding_duration_ms": 234,
        "handoff_detection_duration_ms": 156,
    },
    "quality_scores": {
        "avg_category_confidence": 0.914,
        "avg_intent_confidence": 0.895,
        "avg_handoff_confidence": 0.978,
    },
    "distribution": {
        "categories": 14,
        "intents": 44,
        "items_with_handoff": 1,
        "items_without_handoff": 9,
    },
    "user_corrections": {
        "total_corrections": 1,
        "category_renames": 2,
        "intent_merges": 1,
    }
}
```

---

## 8. Error Handling Examples

### Common Error Responses

```json
{
  "status": "error",
  "error_code": "INVALID_JSON",
  "message": "Uploaded file is not valid JSON",
  "details": {
    "line": 15,
    "column": 5,
    "error": "Expecting comma delimiter"
  }
}
```

```json
{
  "status": "error",
  "error_code": "INVALID_FORMAT",
  "message": "JSON must be a list of objects with 'question' and 'answer' fields",
  "expected_format": {
    "type": "array",
    "items": {
      "type": "object",
      "required": ["question", "answer"]
    }
  }
}
```

```json
{
  "status": "error",
  "error_code": "EMBEDDING_FAILED",
  "message": "Failed to generate embeddings for some questions",
  "failed_indices": [3, 7, 12],
  "suggestion": "Check if questions are too long (max 512 tokens)"
}
```

---

## 9. Integration with Existing Ingestion

### Current flow:
```
Upload Document → Extract Q&A → Confirm → Ingest to DB
```

### New flow:
```
Upload qa.json → Analyze (Generate Metadata) → Review → Confirm → Ingest with Metadata
```

### Backward compatibility:
- Old Q&A pairs without metadata get default category="unknown", intent="unknown"
- Handoff defaults to false
- All timestamps auto-filled

---

## 10. CLI Commands (future enhancements)

```bash
# Analyze a local JSON file
python scripts/generate_metadata.py --file qa.json --num-categories 15 --num-intents 3

# Generate metadata and save to file
python scripts/generate_metadata.py --file qa.json --output qa_with_metadata.json --auto-confirm

# Migrate existing documents
python scripts/auto_metadata_migration.py --batch-size 100

# Validate metadata consistency
python scripts/validate_metadata.py

# Export analysis results
python scripts/export_analysis.py --analysis-id <uuid> --format csv
```

