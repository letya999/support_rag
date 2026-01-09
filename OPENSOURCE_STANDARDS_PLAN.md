# План: Превращение Support RAG в образцовый Open Source проект

**Статус:** Analysis & Planning Document
**Дата:** 2026-01-09
**Исключено:** CI/CD, автотесты, линтеры, GitHub Actions, теги/версионирование

---

## 📋 Содержание

1. [Критические документы](#1-критические-документы)
2. [Метаданные проекта](#2-метаданные-проекта)
3. [Документация для разработчиков](#3-документация-для-разработчиков)
4. [Процесс контрибьютинга](#4-процесс-контрибьютинга)
5. [Улучшение качества кода](#5-улучшение-качества-кода)
6. [Примеры и демонстрация](#6-примеры-и-демонстрация)
7. [Безопасность и правовые документы](#7-безопасность-и-правовые-документы)

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
  - Через pip (после pyproject.toml)
  - Через Docker
  - Из исходников (с git clone)
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

## 2. Метаданные проекта

### 2.1 pyproject.toml (ПРИОРИТЕТ: 🟠 ВЫСОКИЙ)

**Цель:** Стандартизация Python пакета, возможность `pip install`

**Содержит:**
- [ ] Метаданные проекта:
  ```toml
  [project]
  name = "support-rag"
  version = "0.1.0"  # semantic versioning
  description = "RAG system with semantic caching, guardrails, and Telegram integration"
  authors = [{name = "...", email = "..."}]
  readme = "README.md"
  requires-python = ">=3.9,<3.13"
  license = {text = "MIT"}
  keywords = ["rag", "nlp", "semantic-search", "llm", "langgraph"]
  classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Web Environment",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: Text Processing :: Linguistic",
  ]
  ```

- [ ] Зависимости (из requirements.txt):
  ```toml
  dependencies = [
    "langgraph>=1.0.5",
    "langchain>=1.2.0",
    "fastapi>=0.128.0",
    # ... остальное
  ]
  ```

- [ ] Optional зависимости (extras):
  ```toml
  [project.optional-dependencies]
  telegram = ["aiogram>=3.0"]
  dev = ["pytest>=7.0", "black>=22.0"]
  docs = ["sphinx>=4.0", "sphinx-rtd-theme"]
  ```

- [ ] URLs (в проекте):
  ```toml
  [project.urls]
  "Homepage" = "https://github.com/letya999/support_rag"
  "Documentation" = "https://github.com/letya999/support_rag/blob/main/README.md"
  "Repository" = "https://github.com/letya999/support_rag.git"
  "Issues" = "https://github.com/letya999/support_rag/issues"
  ```

- [ ] Entry points (если нужны CLI команды):
  ```toml
  [project.scripts]
  support-rag-ingest = "app.scripts.ingest:main"
  support-rag-server = "app.main:run_server"
  ```

- [ ] Build system:
  ```toml
  [build-system]
  requires = ["setuptools>=45", "wheel"]
  build-backend = "setuptools.build_meta"
  ```

---

### 2.2 .editorconfig (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

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
  pip install -e .  # из pyproject.toml
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

## 4. Процесс контрибьютинга

### 4.1 CONTRIBUTING.md (ПРИОРИТЕТ: 🟠 ВЫСОКИЙ)

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

### 4.2 .github/pull_request_template.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

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

### 4.3 .github/ISSUE_TEMPLATE/ (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

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

## 5. Улучшение качества кода

### 5.1 Заменить print() на structured logging (ПРИОРИТЕТ: 🔴 КРИТИЧЕСКИЙ)

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

### 5.2 Добавить comprehensive docstrings (ПРИОРИТЕТ: 🟠 ВЫСОКИЙ)

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

### 5.3 Добавить type hints аннотации (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Хорошая новость:** Type hints уже широко используются

**Что улучшить:**
- [ ] Добавить возвращаемые типы для всех функций (есть в большинстве)
- [ ] Использовать `TypedDict` для сложных словарей вместо `Dict[str, Any]`
- [ ] Добавить `Optional` где нужно
- [ ] Документировать Generics если есть

---

### 5.4 Code quality improvements (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

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

## 6. Примеры и демонстрация

### 6.1 examples/ папка (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

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

### 6.2 docs/QUICKSTART.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**5-минутный старт:**
1. Docker Compose up
2. Загрузить Q&A данные
3. Сделать RAG запрос
4. Посмотреть результат

---

## 7. Безопасность и правовые документы

### 7.1 SECURITY.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Цель:** Как сообщать об уязвимостях ответственно

**Содержит:**
- [ ] НЕ создавайте публичные issues для безопасности!
- [ ] Email для privacy disclosure: security@example.com
- [ ] PGP ключ (если есть)
- [ ] Процесс: отправить → получить ответ за N дней → fix → release → disclosure
- [ ] Спасибо тем кто нашел уязвимости (security researchers)

---

### 7.2 CODE_OF_CONDUCT.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

**Цель:** Создать приветливую среду для всех

**Можно использовать:** [Contributor Covenant](https://www.contributor-covenant.org/)

---

### 7.3 CHANGELOG.md (ПРИОРИТЕТ: 🟡 СРЕДНИЙ)

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
| pyproject.toml | 🟠 ВЫСОКИЙ | Низкая | 1 |
| Replace print() with logging | 🔴 КРИТИЧЕСКИЙ | Средняя | 2-3 |
| docs/ARCHITECTURE.md | 🟠 ВЫСОКИЙ | Средняя | 2-3 |
| docs/API.md | 🟠 ВЫСОКИЙ | Средняя | 2-3 |
| CONTRIBUTING.md | 🟠 ВЫСОКИЙ | Низкая | 1 |
| Add docstrings | 🟠 ВЫСОКИЙ | Высокая | 4-6 |
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
4. Создать pyproject.toml
5. Заменить print() на logging

### Волна 2 (День 3-5) - Основная документация:
6. Написать CONTRIBUTING.md
7. Создать docs/ARCHITECTURE.md
8. Создать docs/API.md
9. Добавить comprehensive docstrings
10. Создать .github/pull_request_template.md

### Волна 3 (День 6-7) - Дополнительно:
11. Написать docs/DEPLOYMENT.md
12. Написать docs/DATABASE_SCHEMA.md
13. Создать examples/
14. Добавить SECURITY.md, CODE_OF_CONDUCT.md
15. Создать CHANGELOG.md

---

## ✅ Критерии успеха

Проект будет образцовым open-source когда:

- [ ] README.md привлекает новых пользователей
- [ ] DEVELOPMENT.md позволяет новым контрибьюторам стартовать за <30 минут
- [ ] Все публичные функции имеют docstrings с примерами
- [ ] Логирование структурировано (JSON, не print statements)
- [ ] CONTRIBUTING.md четко объясняет процесс
- [ ] docs/ папка содержит полную документацию
- [ ] examples/ показывают реальные сценарии использования
- [ ] LICENSE определяет условия использования
- [ ] pyproject.toml позволяет установить как pip пакет
- [ ] SECURITY.md объясняет как сообщать об уязвимостях

---

## 📝 Заметки

**Исключено по запросу:**
- ❌ CI/CD (GitHub Actions)
- ❌ Автотесты (pytest, coverage)
- ❌ Линтеры (flake8, pylint, black)
- ❌ Semantic versioning tags
- ❌ Автоматизированный release процесс

**Если позже понадобится добавить:**
- `.github/workflows/tests.yml` для автотестов
- `.flake8`, `mypy.ini` для инструментов качества
- Semantic versioning для releases
- бейджи в README для этого

---

**Документ подготовлен:** 2026-01-09
**Статус:** Planning & Analysis
**Следующий шаг:** Начать реализацию с Волны 1
