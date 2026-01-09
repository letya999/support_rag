# План: Превращение Support RAG в образцовый Open Source проект

**Статус:** Analysis & Planning Document
**Дата:** 2026-01-09
**Исключено:** CI/CD, автотесты, линтеры, GitHub Actions, теги/версионирование

---

## 📋 Содержание

1. [Критические документы](#1-критические-документы)
2. [Конфигурация проекта](#2-конфигурация-проекта)
3. [Документация для разработчиков](#3-документация-для-разработчиков)
4. [REST API и Webhooks документация](#4-rest-api-и-webhooks-документация)
5. [Процесс контрибьютинга](#5-процесс-контрибьютинга)
6. [Улучшение качества кода](#6-улучшение-качества-кода)
7. [Примеры и демонстрация](#7-примеры-и-демонстрация)
8. [Безопасность и правовые документы](#8-безопасность-и-правовые-документы)

---

## 1. Критические документы

### 1.1 README.md (ПРИОРИТЕТ: 🔴 КРИТИЧЕСКИЙ)

**Цель:** Превая точка входа для всех пользователей GitHub

**Содержит:**
- [ ] Логотип/название проекта с кратким описанием (1-2 строки)
- [ ] Значки (badges): License, Language, Latest Release, Downloads
- [ ] Оглавление (Table of Contents)
- [ ] Зачем это нужно (Why Support RAG?)
- [ ] Ключевые возможности (Key Features) - 5-7 с иконками/эмодзи
- [ ] Скриншоты или демонстрация результатов работы
- [ ] Быстрый старт (Quick Start) - 5 шагов максимум
- [ ] Архитектурная диаграмма (ASCII или ссылка на ARCHITECTURE.md)
- [ ] Примеры использования (2-3 практических примера)
- [ ] Требования (Requirements): Python версия, зависимости
- [ ] Установка (Installation):
  - Через Docker (рекомендуется)
  - Из исходников с requirements.txt (для локальной разработки)
  - Системные зависимости (PostgreSQL, Redis для полного функционала)
- [ ] Использование (Usage):
  - Как запустить API
  - Как запустить Telegram бот
  - Базовый пример RAG запроса
- [ ] Ссылки на документацию:
  - Development Guide → DEVELOPMENT.md
  - API Documentation → docs/API.md
  - Architecture → docs/ARCHITECTURE.md
- [ ] FAQ (5-7 частых вопросов)
- [ ] Контрибьютинг (Contributing) - ссылка на CONTRIBUTING.md
- [ ] Лицензия - ссылка на LICENSE
- [ ] Контакты/Поддержка

**Структура:**
```
README.md
├── Header (Logo + 1-line description)
├── Badges
├── Table of Contents
├── What is Support RAG?
├── Key Features (5-7 items)
├── Screenshots/Demo
├── Quick Start (Docker Compose)
├── Project Structure (brief)
├── Installation
├── Usage Examples
├── Configuration
├── Documentation Links
├── FAQ
├── Contributing
├── License
└── Support
```

---

### 1.2 LICENSE (ПРИОРИТЕТ: 🔴 КРИТИЧЕСКИЙ)

**Цель:** Юридическая защита и явное определение условий использования

**Опции:**
- [ ] MIT License (самый популярный для open-source, permissive)
- [ ] Apache 2.0 (с явной защитой от патентов)
- [ ] GPL v3 (если хотите copyleft)

**Действие:** Выбрать одну, создать файл LICENSE с полным текстом

**Примечание:** MIT лучше всего подходит для open-source инструментов

---

## 2. Конфигурация проекта

### 2.1 .editorconfig (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Цель:** Единообразное форматирование кода в разных редакторах

```
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.py]
indent_style = space
indent_size = 4
max_line_length = 88

[*.{yml,yaml}]
indent_style = space
indent_size = 2

[*.md]
trim_trailing_whitespace = false
```

---

## 3. Документация для разработчиков

### 3.1 DEVELOPMENT.md (ПРИОРИТЕТ: 🔴 КРИТИЧЕСКИЙ)

**Цель:** Руководство для новых контрибьюторов и разработчиков

**Содержит:**
- [ ] Prerequisites (Python 3.9+, Docker, PostgreSQL, Redis)
- [ ] Локальная установка (step-by-step):
  ```bash
  git clone https://github.com/letya999/support_rag.git
  cd support_rag
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt  # Все зависимости
  cp .env.example .env
  # Заполнить .env файл
  ```
- [ ] Запуск сервисов (Docker Compose):
  ```bash
  docker-compose up -d
  ```
- [ ] Инициализация БД:
  ```bash
  python scripts/run_migrations.py
  python scripts/ingest.py --file datasets/qa_data.json
  ```
- [ ] Запуск разработки:
  ```bash
  uvicorn app.main:app --reload
  ```
- [ ] Проверка здоровья API (health check)
- [ ] Загрузка моделей (download_models.py)
- [ ] Структура кода (описание каждой папки)
- [ ] Как добавить новый Node:
  - Копировать шаблон из existing node
  - Реализовать INPUT/OUTPUT контракты
  - Добавить config.yaml
  - Интегрировать в pipeline_order.yaml
- [ ] Debugging и troubleshooting
- [ ] Полезные команды:
  ```bash
  python scripts/bench_modular.py  # Performance testing
  python scripts/reset_db.py       # Clean reset
  ```

---

### 3.2 docs/ARCHITECTURE.md (ПРИОРИТЕТ: 🟠 ВЫСОКИЙ)

**Цель:** Глубокое понимание системы архитектуры

**Содержит:**
- [ ] Обзор система (2-3 абзаца)
- [ ] Диаграмма потока данных (ASCII или Mermaid):
  ```
  User Query
      ↓
  Input Guardrails → Language Detection
      ↓
  Check Cache → Cache Similarity
      ↓
  Classification (Easy/Semantic)
      ↓
  Hybrid Search (Lexical + Vector)
      ↓
  Reranking → Multi-hop Reasoning
      ↓
  Result Fusion
      ↓
  LLM Generation
      ↓
  Output Guardrails
      ↓
  Archive Session
  ```

- [ ] 29 Node компонентов:
  - Для каждого node:
    - Назначение (1 строка)
    - Input (контракт)
    - Output (контракт)
    - Конфигурируемые параметры
    - Зависимости

- [ ] Storage Layer:
  - PostgreSQL (структура таблиц)
  - Qdrant (вектор индексы)
  - Redis (кеш)

- [ ] Работа с состоянием (State Management):
  - TypedDict структура
  - Reducers (overwrite, keep_latest, merge_unique)
  - Как редукторы работают

- [ ] Интеграции:
  - OpenAI API
  - Sentence-Transformers
  - Telegram Bot API
  - Langfuse (observability)

- [ ] Конфигурация:
  - Как работает YAML-based config
  - Иерархия (global → node → runtime)

- [ ] Caching стратегия

- [ ] Error Handling:
  - Custom exceptions
  - Try-except в BaseNode
  - Contract validation

---

### 3.3 docs/API.md (ПРИОРИТЕТ: 🟠 ВЫСОКИЙ)

**Цель:** Полная документация всех API endpoints

**Содержит:**
- [ ] Base URL, Authentication (если есть)
- [ ] Для каждого endpoint:
  ```markdown
  ### POST /rag/query

  **Description:** Execute RAG query with conversation history

  **Request:**
  ```json
  {
    "question": "string (required)",
    "session_id": "string (optional)",
    "history": [{"role": "user|assistant", "content": "..."}],
    "search_type": "hybrid|lexical|vector"
  }
  ```

  **Response (200):**
  ```json
  {
    "answer": "string",
    "sources": [{"title": "...", "content": "...", "score": 0.95}],
    "session_id": "uuid",
    "execution_time_ms": 1234,
    "confidence": 0.92
  }
  ```

  **Error Responses:**
  - 400: Invalid input
  - 429: Rate limited
  - 500: Internal error

  **Example cURL:**
  ```bash
  curl -X POST http://localhost:8000/rag/query \
    -H "Content-Type: application/json" \
    -d '{"question": "How to install?"}'
  ```
  ```

- [ ] Все 10 endpoints с примерами
- [ ] Rate limiting информация
- [ ] Authentication (если применимо)
- [ ] Возможные ошибки и их коды

---

### 3.4 docs/DATABASE_SCHEMA.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Цель:** Документация структуры БД

**Содержит:**
- [ ] Обзор PostgreSQL схемы
- [ ] Таблицы:
  - documents (ID, title, content, metadata)
  - qa_pairs (question, answer, document_id)
  - sessions (session_id, user_id, created_at)
  - cache_entries (query, response, timestamp)
  - embeddings (vector storage в pgvector)

- [ ] Для каждой таблицы:
  - Структура (columns, types)
  - Индексы
  - Constraints
  - Relationships (FK)

- [ ] Qdrant Collection schemas (для вектор поиска)
- [ ] Redis key patterns
- [ ] Миграции (what changed in v0.1.0, v0.2.0, etc.)

---

### 3.5 docs/DEPLOYMENT.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Цель:** Как развернуть в production

**Содержит:**
- [ ] Требования к серверу (CPU, RAM, GPU if needed)
- [ ] Docker Compose для production (с environment переменными)
- [ ] Manual deployment (без Docker)
- [ ] Environment переменные (с описанием каждой)
- [ ] Backup стратегия (PostgreSQL, Qdrant)
- [ ] Масштабирование (horizontal scaling considerations)
- [ ] Monitoring и логирование
- [ ] SSL/HTTPS настройка
- [ ] Firewall rules
- [ ] Health check endpoints
- [ ] Graceful shutdown
- [ ] Emergency procedures (что делать если сломалось)

---

### 3.6 docs/CONFIGURATION.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Цель:** Документация всей системы конфигурации

**Содержит:**
- [ ] Как работает config system (YAML + Python merge)
- [ ] Global параметры (global.yaml)
- [ ] Node-specific configs
- [ ] Runtime override (если поддерживается)
- [ ] Все доступные параметры с описанием:
  - Thresholds (classification, confidence)
  - Timeouts
  - Cache settings
  - Language settings
  - Intent registry
  - System phrases
- [ ] Примеры модификации конфига
- [ ] Hot reload (POST /config/reload)

---

## 4. REST API и Webhooks документация

### 4.1 docs/API.md - REST API (ПРИОРИТЕТ: 🟠 ВЫСОКИЙ)

**Цель:** Полная документация всех REST API endpoints

**Содержит:**
- [ ] Base URL и общая информация
- [ ] Для каждого endpoint (GET, POST, DELETE и т.д.):
  ```markdown
  ### POST /rag/query

  **Description:** Execute RAG query with conversation history

  **Request Body:**
  ```json
  {
    "question": "string (required)",
    "session_id": "string (optional)",
    "history": [{"role": "user|assistant", "content": "..."}],
    "search_type": "hybrid|lexical|vector"
  }
  ```

  **Response (200):**
  ```json
  {
    "answer": "string",
    "sources": [{"title": "...", "content": "...", "score": 0.95}],
    "session_id": "uuid",
    "execution_time_ms": 1234,
    "confidence": 0.92
  }
  ```

  **Error Responses:**
  - 400: Invalid input
  - 429: Rate limited
  - 500: Internal error

  **Example cURL:**
  ```bash
  curl -X POST http://localhost:8000/rag/query \
    -H "Content-Type: application/json" \
    -d '{"question": "How to install?"}'
  ```
  ```

- [ ] Все существующие endpoints с примерами
- [ ] Rate limiting и throttling информация
- [ ] Authentication (если применимо)
- [ ] Возможные ошибки и их коды
- [ ] Версионирование API (если несколько версий)

**Формат:** Markdown с JSON примерами (более простой чем Swagger для быстрого чтения)

---

### 4.2 docs/WEBHOOKS.md - Webhook Events (ПРИОРИТЕТ: 🟠 ВЫСОКИЙ)

**Цель:** Документация webhook событий, когда они срабатывают, как их интегрировать

**Содержит:**

#### Основная информация:
- [ ] Что такое webhooks в этом проекте
- [ ] Как их включить/отключить
- [ ] Процесс регистрации webhook URL
- [ ] Аутентификация (HMAC署名, API ключ или другое)
- [ ] Retry стратегия (как часто пытаться отправить при failure)
- [ ] Timeout настройки

#### Для каждого webhook события:
```markdown
### Event: document.processed

**Когда срабатывает:** После успешной обработки и индексации документа

**Payload:**
```json
{
  "event": "document.processed",
  "timestamp": "2026-01-09T10:30:45Z",
  "document_id": "uuid",
  "document_title": "string",
  "status": "success|failed",
  "metadata": {
    "chunks_created": 42,
    "embeddings_generated": 42,
    "qa_pairs_extracted": 15,
    "processing_time_ms": 1234
  },
  "error": "nullable string"
}
```

**Retry Policy:**
- Up to 5 retries
- Exponential backoff: 1s, 2s, 4s, 8s, 16s

**Example Webhook Handler (Python):**
```python
from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib

app = FastAPI()

@app.post("/webhook/support-rag")
async def handle_webhook(request: Request):
    # Verify signature
    signature = request.headers.get("X-Webhook-Signature")
    body = await request.body()

    expected_sig = hmac.new(
        b"your-secret-key",
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    # Process event
    if payload["event"] == "document.processed":
        handle_document_processed(payload)

    return {"status": "received"}

def handle_document_processed(payload):
    print(f"Document {payload['document_id']} processed with {payload['metadata']['chunks_created']} chunks")
    # Your custom logic here
```
```

**Events List:**
- [ ] `document.uploaded` - При загрузке файла
- [ ] `document.processing_started` - Начало обработки
- [ ] `document.processed` - Успешная обработка
- [ ] `document.processing_failed` - Ошибка обработки
- [ ] `qa_pair.created` - Создание пары вопрос-ответ
- [ ] `session.started` - Начало новой сессии (Telegram)
- [ ] `session.ended` - Завершение сессии

---

### 4.3 Webhook Specification (AsyncAPI) - (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Файл:** `docs/webhooks-spec.yaml` - Машиночитаемая спецификация webhook событий

**Формат:** AsyncAPI 3.0 (стандарт как OpenAPI для асинхронных API)

**Цель:** Для автоматического генерирования SDK и клиентов

**Содержит:**
```yaml
asyncapi: '3.0.0'
info:
  title: Support RAG Webhooks API
  version: '1.0.0'
  description: Real-time events from Support RAG system

servers:
  production:
    url: 'https://api.support-rag.example.com'
    description: Production environment

channels:
  # Webhook subscription endpoint
  webhooks:
    address: '/webhooks/subscribe'
    description: 'Subscribe to webhook events'
    subscribe:
      operationId: subscribeToWebhooks
      message:
        contentType: application/json
        payload:
          type: object
          properties:
            url:
              type: string
              format: uri
              description: 'Your webhook URL'
            events:
              type: array
              items:
                type: string
                enum:
                  - document.uploaded
                  - document.processed
                  - document.processing_failed
                  - qa_pair.created
                  - session.started
                  - session.ended
            secret:
              type: string
              description: 'Optional secret for HMAC signature'

  # Webhook delivery channels (events sent to your URL)
  documentProcessed:
    address: 'https://your-webhook-url.com/webhook'
    description: 'Webhook event: document processed'
    publish:
      operationId: onDocumentProcessed
      message:
        contentType: application/json
        headers:
          type: object
          properties:
            X-Webhook-Signature:
              type: string
              description: 'HMAC-SHA256 signature for verification'
            X-Webhook-Delivery-Id:
              type: string
              format: uuid
              description: 'Unique delivery ID for idempotency'
        payload:
          type: object
          properties:
            event:
              type: string
              enum: [document.processed]
            timestamp:
              type: string
              format: date-time
            document_id:
              type: string
              format: uuid
            status:
              type: string
              enum: [success, failed]
            metadata:
              type: object
              properties:
                chunks_created:
                  type: integer
                embeddings_generated:
                  type: integer
                processing_time_ms:
                  type: integer
```

**Инструменты для просмотра AsyncAPI:**
- Online editor: https://studio.asyncapi.com/ (вставить YAML)
- CLI: `npm install -g @asyncapi/cli` → `asyncapi generate fromTemplate webhooks-spec.yaml @asyncapi/html-template -o docs/webhooks-html`

---

### 4.4 REST API OpenAPI Spec - (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Файл:** `docs/api-spec.yaml` - Машиночитаемая спецификация REST API

**Формат:** OpenAPI 3.0 (стандартный формат для REST API документации)

**Цель:**
- Автоматическое генерирование Swagger UI
- Поддержка IDE для автодополнения
- Генерирование клиентских SDK

**Генерирование из FastAPI:**
```python
# app/main.py
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="Support RAG API",
    description="RAG system with semantic caching and webhooks",
    version="1.0.0"
)

# Endpoints будут автоматически добавлены в OpenAPI схему

# Экспорт спецификации
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Support RAG",
        version="1.0.0",
        description="Full documentation at /docs",
        routes=app.routes,
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

**Автоматический доступ:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Raw OpenAPI JSON: `http://localhost:8000/openapi.json`

---

## 5. Процесс контрибьютинга

### 5.1 CONTRIBUTING.md (ПРИОРИТЕТ: 🟠 ВЫСОКИЙ)

**Цель:** Четкие правила для контрибьюторов

**Содержит:**
- [ ] Философия проекта (в 1-2 абзацах)
- [ ] Как начать контрибьютить:
  - Fork → Clone → Branch → Commit → Push → PR
- [ ] Правила именования ветвей:
  - Feature: `feature/short-description`
  - Bug: `bugfix/issue-number`
  - Docs: `docs/what-changed`
  - Refactor: `refactor/component-name`

- [ ] Commit сообщения (Conventional Commits):
  ```
  <type>(<scope>): <subject>

  - feat(nodes): add new reranking model support
  - fix(cache): resolve null pointer in similarity check
  - docs(api): clarify response format
  - refactor(pipeline): simplify state initialization
  - perf(search): optimize vector indexing
  ```

- [ ] Pull Request процесс:
  - Заполнить PR template
  - Описание изменений
  - Как тестировали
  - Breaking changes (если есть)

- [ ] Code style:
  - PEP 8 (4 spaces indent)
  - Max line length: 88
  - Type hints обязательны для новых функций
  - Docstrings для публичных функций

- [ ] Что НЕ принимается:
  - Форматирование без логики
  - Беззависимые изменения

- [ ] Review process:
  - Maintainers проверяют PR за N дней
  - Требует N одобрений

- [ ] Release process (краткое описание)

---

### 5.2 .github/pull_request_template.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Цель:** Стандартизация PR описания

```markdown
## Description
Brief description of what this PR does

## Type of Change
- [ ] New feature
- [ ] Bug fix
- [ ] Documentation update
- [ ] Refactoring
- [ ] Performance improvement

## Related Issues
Fixes #(issue number)

## How Has This Been Tested?
Describe the tests you ran

## Checklist
- [ ] Code follows project style guidelines
- [ ] Added/updated docstrings
- [ ] Changes are backward compatible
- [ ] No print() statements (use logging)
- [ ] Type hints added for new functions
```

---

### 5.3 .github/ISSUE_TEMPLATE/ (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Шаблоны для трех типов issues:**

#### bug_report.md
```markdown
## Describe the bug
Clear description

## Steps to Reproduce
1. ...
2. ...

## Expected behavior
What should happen

## Actual behavior
What happens instead

## Environment
- Python version
- OS
- Docker version (if relevant)

## Logs
```

#### feature_request.md
```markdown
## Is this related to a problem?
Description

## Describe the solution
What you'd like to happen

## Alternative solutions
Other approaches you've considered

## Additional context
Any other information
```

#### question.md (для discussions)
```markdown
## Question
What are you asking?

## Context
Where did you encounter this?

## What have you tried?
Steps you've taken
```

---

## 6. Улучшение качества кода

### 6.1 Заменить print() на structured logging (ПРИОРИТЕТ: 🔴 КРИТИЧЕСКИЙ)

**Проблема:** Множество `print("🚀 Starting...")` по всему коду

**Решение:**
- [ ] Создать `app/logging_config.py`:
  ```python
  import logging
  from pythonjsonlogger import jsonlogger

  logger = logging.getLogger("support_rag")

  def setup_logging():
      handler = logging.StreamHandler()
      formatter = jsonlogger.JsonFormatter()
      handler.setFormatter(formatter)
      logger.addHandler(handler)
      logger.setLevel(logging.INFO)
  ```

- [ ] Заменить все `print()` на `logger.info()`, `logger.warning()`, `logger.error()`
- [ ] Примеры замен:
  - `print("🚀 Starting...")` → `logger.info("Application startup", extra={"status": "starting"})`
  - `print(f"Loaded {n} models")` → `logger.info("Models loaded", extra={"count": n})`

---

### 6.2 Добавить comprehensive docstrings (ПРИОРИТЕТ: 🟠 ВЫСОКИЙ)

**Цель:** Все публичные функции и классы должны иметь docstrings

**Стиль:** Google-style docstrings

```python
class BaseNode(ABC):
    """Abstract base class for all pipeline nodes.

    This class defines the contract that all nodes must follow, including
    input/output validation and execution framework.

    Attributes:
        INPUT_CONTRACT: Dictionary defining required and optional inputs
        OUTPUT_CONTRACT: Dictionary defining guaranteed and conditional outputs

    Example:
        >>> class MyNode(BaseNode):
        ...     INPUT_CONTRACT = {"required": ["question"]}
        ...     OUTPUT_CONTRACT = {"guaranteed": ["response"]}
        ...
        ...     async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        ...         return {"response": "answer"}
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the node with given state.

        Args:
            state: Current pipeline state as dictionary

        Returns:
            Updated state dictionary with node outputs

        Raises:
            ValidationError: If input contract is violated

        Note:
            This method is called by the pipeline orchestrator.
            Don't call directly in user code.
        """
```

**Что добавить:**
- [ ] Docstrings для всех классов в `app/nodes/base_node/`
- [ ] Docstrings для всех публичных функций в `app/services/`
- [ ] Module-level docstrings для каждого файла (зачем этот модуль)
- [ ] Примеры использования (Example sections)

---

### 6.3 Добавить type hints аннотации (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Хорошая новость:** Type hints уже широко используются

**Что улучшить:**
- [ ] Добавить возвращаемые типы для всех функций (есть в большинстве)
- [ ] Использовать `TypedDict` для сложных словарей вместо `Dict[str, Any]`
- [ ] Добавить `Optional` где нужно
- [ ] Документировать Generics если есть

---

### 6.4 Code quality improvements (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

- [ ] Удалить все TODO комментарии (закончить или создать issues)
- [ ] Удалить закомментированный dead code
- [ ] Разделить большие функции (если >50 строк)
- [ ] Заменить magic numbers на named constants:
  ```python
  # Вместо:
  if confidence > 0.85:

  # Писать:
  MIN_CONFIDENCE_THRESHOLD = 0.85
  if confidence > MIN_CONFIDENCE_THRESHOLD:
  ```

---

## 7. Примеры и демонстрация

### 7.1 examples/ папка (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Структура:**
```
examples/
├── 01_simple_query.py          # Basic RAG query
├── 02_with_history.py          # Multi-turn conversation
├── 03_document_ingestion.py    # Upload & ingest documents
├── 04_custom_node.py           # How to create custom node
├── 05_config_override.py       # Custom configuration
└── README.md                    # Как запустить примеры
```

**Каждый пример:**
- Полностью рабочий код
- Комментарии объясняющие шаги
- Требования (какие сервисы должны быть запущены)
- Ожидаемый output

---

### 7.2 docs/QUICKSTART.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**5-минутный старт:**
1. Docker Compose up
2. Загрузить Q&A данные
3. Сделать RAG запрос
4. Посмотреть результат

---

## 8. Безопасность и правовые документы

### 8.1 SECURITY.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Цель:** Как сообщать об уязвимостях ответственно

**Содержит:**
- [ ] НЕ создавайте публичные issues для безопасности!
- [ ] Email для privacy disclosure: security@example.com
- [ ] PGP ключ (если есть)
- [ ] Процесс: отправить → получить ответ за N дней → fix → release → disclosure
- [ ] Спасибо тем кто нашел уязвимости (security researchers)

---

### 8.2 CODE_OF_CONDUCT.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Цель:** Создать приветливую среду для всех

**Можно использовать:** [Contributor Covenant](https://www.contributor-covenant.org/)

---

### 8.3 CHANGELOG.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Цель:** История изменений для каждой версии

**Формат: Keep a Changelog**

```markdown
# Changelog

## [0.1.0] - 2026-01-09
### Added
- Initial release
- Support for 29 node pipeline
- Telegram bot integration
- Semantic caching

### Fixed
- Silent pipeline failures (BaseNode try-except)

### Changed
- Updated translation module

[Unreleased]: https://github.com/letya999/support_rag/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/letya999/support_rag/releases/tag/v0.1.0
```

---

## 📊 Сводная таблица приоритетов

| Документ | Приоритет | Сложность | Время (часы) |
|----------|-----------|-----------|-------------|
| README.md | 🔴 КРИТИЧЕСКИЙ | Средняя | 2-3 |
| LICENSE | 🔴 КРИТИЧЕСКИЙ | Низкая | 0.25 |
| DEVELOPMENT.md | 🔴 КРИТИЧЕСКИЙ | Низкая | 1-2 |
| Replace print() with logging | 🔴 КРИТИЧЕСКИЙ | Средняя | 2-3 |
| docs/ARCHITECTURE.md | 🟠 ВЫСОКИЙ | Средняя | 2-3 |
| docs/API.md (REST API docs) | 🟠 ВЫСОКИЙ | Средняя | 2-3 |
| docs/WEBHOOKS.md (Events documentation) | 🟠 ВЫСОКИЙ | Средняя | 2 |
| CONTRIBUTING.md | 🟠 ВЫСОКИЙ | Низкая | 1 |
| Add docstrings | 🟠 ВЫСОКИЙ | Высокая | 4-6 |
| docs/webhooks-spec.yaml (AsyncAPI) | 🟡 СРЕДНИЙ | Средняя | 1-2 |
| docs/api-spec.yaml (OpenAPI) | 🟡 СРЕДНИЙ | Низкая | 1 |
| docs/DATABASE_SCHEMA.md | 🟡 СРЕДНИЙ | Низкая | 1-2 |
| docs/DEPLOYMENT.md | 🟡 СРЕДНИЙ | Средняя | 1-2 |
| docs/CONFIGURATION.md | 🟡 СРЕДНИЙ | Низкая | 1 |
| .editorconfig | 🟡 СРЕДНИЙ | Низкая | 0.25 |
| .github/pull_request_template.md | 🟡 СРЕДНИЙ | Низкая | 0.5 |
| .github/ISSUE_TEMPLATE/ | 🟡 СРЕДНИЙ | Низкая | 0.5 |
| examples/ | 🟡 СРЕДНИЙ | Средняя | 2 |
| SECURITY.md | 🟡 СРЕДНИЙ | Низкая | 0.5 |
| CODE_OF_CONDUCT.md | 🟡 СРЕДНИЙ | Низкая | 0.25 |
| CHANGELOG.md | 🟡 СРЕДНИЙ | Низкая | 0.5 |
| Type hints improvements | 🟡 СРЕДНИЙ | Средняя | 1-2 |

---

## 🎯 Рекомендуемый порядок реализации

### Волна 1 (День 1-2) - Критически важное:
1. Добавить LICENSE
2. Написать README.md
3. Написать DEVELOPMENT.md
4. Заменить print() на structured logging

### Волна 2 (День 3-5) - Основная документация для API:
5. Написать CONTRIBUTING.md
6. Создать docs/ARCHITECTURE.md
7. Создать docs/API.md (REST API endpoints)
8. Создать docs/WEBHOOKS.md (Webhook events documentation)
9. Добавить comprehensive docstrings
10. Создать .github/pull_request_template.md

### Волна 3 (День 6-7) - Спецификации и дополнительно:
11. Создать docs/webhooks-spec.yaml (AsyncAPI спец)
12. Создать docs/api-spec.yaml (OpenAPI спец - генерируется из FastAPI)
13. Написать docs/DEPLOYMENT.md
14. Написать docs/DATABASE_SCHEMA.md
15. Создать examples/
16. Добавить SECURITY.md, CODE_OF_CONDUCT.md
17. Создать CHANGELOG.md
18. Создать .editorconfig

---

## ✅ Критерии успеха

Проект будет образцовым open-source когда:

- [ ] README.md привлекает новых пользователей
- [ ] DEVELOPMENT.md позволяет новым контрибьюторам стартовать за <30 минут
- [ ] Все публичные функции имеют docstrings с примерами
- [ ] Логирование структурировано (JSON, не print statements)
- [ ] CONTRIBUTING.md четко объясняет процесс
- [ ] docs/ папка содержит полную документацию (API, WEBHOOKS, ARCHITECTURE и т.д.)
- [ ] REST API полностью документирована (docs/API.md + docs/api-spec.yaml)
- [ ] Webhook события полностью документированы (docs/WEBHOOKS.md + docs/webhooks-spec.yaml AsyncAPI)
- [ ] examples/ показывают реальные сценарии использования
- [ ] LICENSE определяет условия использования
- [ ] SECURITY.md объясняет как сообщать об уязвимостях

---

## 📝 Заметки

**Исключено по запросу:**
- ❌ CI/CD (GitHub Actions)
- ❌ Автотесты (pytest, coverage)
- ❌ Линтеры (flake8, pylint, black)
- ❌ pyproject.toml (используется requirements.txt для простоты)
- ❌ Semantic versioning tags
- ❌ Автоматизированный release процесс

**Ключевые решения:**
- ✅ Requirements.txt как основной способ управления зависимостями
- ✅ REST API документирована в docs/API.md (Markdown) + docs/api-spec.yaml (OpenAPI из FastAPI)
- ✅ Webhooks документированы в docs/WEBHOOKS.md (примеры) + docs/webhooks-spec.yaml (AsyncAPI)
- ✅ Structured logging вместо print() - JSON логирование

**Если позже понадобится добавить:**
- `.github/workflows/tests.yml` для автотестов
- `.flake8`, `mypy.ini` для инструментов качества
- pyproject.toml для публикации на PyPI
- Semantic versioning для releases
- бейджи в README для статусов

---

**Документ подготовлен:** 2026-01-09
**Статус:** Planning & Analysis
**Следующий шаг:** Начать реализацию с Волны 1
