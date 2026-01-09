# Отчет по архитектурному аудиту RAG Pipeline

**Дата:** 2026-01-09  
**Анализируемые модули:** `app/services`, `app/pipeline`, `app/observability`, `app/nodes`, `app/integrations`, `app/api`, `app/storage`

---

## Резюме

Выявлено **16 критических архитектурных нарушений** в следующих категориях:
- 🔴 **Нарушения зависимостей (6)**: Сервисы и интеграции зависят от нод
- 🟡 **Нарушения SRP (7)**: Файлы выполняют множественные зоны ответственности
- 🟠 **Смешанные ответственности (3)**: Файлы содержат нечистые функции и бизнес-логику

---

## 🔴 Критические нарушения зависимостей

### 1. `app/storage/vector_store.py` → `app/nodes`

**Файл:** `app/storage/vector_store.py`

**Проблема:**
```python
from app.nodes.retrieval.storage import vector_search as search_documents
from app.nodes.lexical_search.storage import lexical_search_db as lexical_search
```

**Нарушение:**
- Storage-слой (низкоуровневый) импортирует код из nodes (высокоуровневый)
- Нарушается принцип **Dependency Inversion** - зависимости должны быть направлены снизу вверх
- `storage` должен предоставлять примитивы для работы с БД/векторами, а не полагаться на ноды

**Последствия:**
- Циклические зависимости
- Невозможность переиспользовать storage независимо
- Coupling между слоями

**Решение:**
- Выделить переиспользуемую функциональность из `app/nodes/retrieval/storage.py` в `app/storage/vector_operations.py`
- Выделить `app/nodes/lexical_search/storage.py` в `app/storage/lexical_operations.py`
- Ноды остаются в `app/nodes/`, но используют функции из `app/storage/`
- `app/storage/vector_store.py` импортирует из `app/storage/vector_operations.py`, а не из nodes

---

### 2. `app/integrations/translation.py` → `app/nodes`

**Файл:** `app/integrations/translation.py:7`

**Проблема:**
```python
from app.nodes.query_translation.translator import translator
```

**Нарушение:**
- Integration-слой импортирует из nodes
- `translator` — это служебная утилита, которая должна быть в `app/services` или `app/integrations`
- Nodes не должны быть зависимостью для интеграций

**Последствия:**
- Невозможность использовать translation без всей ноды query_translation
- Нарушение изоляции компонентов

**Решение:**
- Переместить `translator` из `app/nodes/query_translation/translator.py` в `app/services/translation/translator.py`
- Нода `query_translation` остается, но использует сервис из `app/services/`
- Обновить импорты в ноде и в `app/integrations/translation.py`

---

### 3. `app/services/metadata_generation/embedding_classifier.py` → `app/nodes`

**Файл:** `app/services/metadata_generation/embedding_classifier.py:10`

**Проблема:**
```python
from app.nodes.easy_classification.semantic_classifier import SemanticClassificationService
```

**Нарушение:**
- Service-слой импортирует из nodes
- `SemanticClassificationService` — это переиспользуемая служба, которая должна быть в `app/services`

**Последствия:**
- Metadata generation зависит от nodes, хотя должен быть независимым сервисом
- Нарушение модульности

**Решение:**
- Переместить `SemanticClassificationService` в `app/services/classification/semantic_service.py`
- Нода `easy_classification` остается в `app/nodes/`, но импортирует сервис из `app/services/`
- Обновить импорты в ноде и в `embedding_classifier.py`

---

### 4. `app/services/cache/session.py` → `app/pipeline`

**Файл:** `app/services/cache/session.py:12`

**Проблема:**
```python
from app.pipeline.config_proxy import conversation_config
```

**Нарушение:**
- Service импортирует конфигурацию из pipeline
- `conversation_config` смешивает конфиги разных нод, должен быть разделен

**Последствия:**
- Сервисы зависят от pipeline-уровня
- Нарушение Dependency Inversion

**Решение:**
- Переместить `conversation_config` в `app/services/config_loader/conversation_config.py`
- Обновить импорты в `session.py` и других файлах

---

### 5. `app/api/routes.py` → `app/nodes`

**Файл:** `app/api/routes.py:13`

**Проблема:**
```python
from app.nodes.retrieval.search import retrieve_context
```

**Нарушение:**
- API напрямую вызывает логику из nodes
- Nodes должны вызываться только через pipeline/graph

**Последствия:**
- API обходит pipeline, нарушая единую точку входа
- Возможны несогласованные состояния

**Решение:**
- API должен вызывать только `rag_graph` или сервисы из `app/services`
- Создать `app/services/search.py` для оборачивания логики поиска

---

### 6. `app/api/routes.py` → множественные зоны ответственности

**Файл:** `app/api/routes.py:314`

**Проблема:**
```python
from app.nodes._shared_config.history_filter import clear_filter_cache
```

**Нарушение:**
- API напрямую вызывает внутренние конфигурационные утилиты нод
- Nodes-специфичная логика не должна быть доступна напрямую из API

**Последствия:**
- Высокая связность между слоями
- API знает о внутренностях nodes

**Решение:**
- Создать централизованный `app/services/config_manager.py` для управления всеми кешами конфигов
- API вызывает сервисы, а не внутренности нод

---

## 🟡 Нарушения принципа единственной ответственности (SRP)

### 7. `app/pipeline/graph.py` - множественные ответственности

**Файл:** `app/pipeline/graph.py`

**Проблема:**
Файл совмещает 5+ ответственностей:

1. **Импорт всех нод** (строки 11-35)
2. **Функции условной маршрутизации** (`cache_hit_logic`, `router_logic`, `should_fast_escalate`, `check_guardrails_outcome`)
3. **Валидация структуры pipeline** (`validate_pipeline_structure`)
4. **Построение графа workflow** (основная логика)
5. **Управление конфигурацией** (чтение yaml, определение активных нод)

**Последствия:**
- Файл 376 строк, сложно поддерживать
- Изменение маршрутизации требует изменения файла построения графа
- Невозможно переиспользовать компоненты

**Решение:**
Разделить на:
- `app/pipeline/graph_builder.py` - построение графа
- `app/pipeline/routing_logic.py` - функции маршрутизации
- `app/pipeline/validators.py` - валидация структуры
- `app/pipeline/node_registry.py` - регистрация нод

---

### 8. `app/api/routes.py` - множественные ответственности (725 строк)

**Файл:** `app/api/routes.py`

**Проблема:**
Файл совмещает 6+ разных API доменов:

1. **RAG pipeline endpoints** (`/search`, `/ask`, `/rag/query`)
2. **Configuration endpoints** (`/config/*`)
3. **Document upload/ingestion** (`/documents/*`)
4. **Metadata generation endpoints** (`/documents/metadata-generation/*`)
5. **Бизнес-логика обработки** (встроенная в endpoints)
6. **Error handling и retry логика**

**Последствия:**
- Файл 725 строк, сложен для навигации
- Смешивание разных доменов в одном файле
- Тяжело тестировать отдельные компоненты

**Решение:**
Разделить на отдельные роутеры:
- `app/api/rag_routes.py` - RAG endpoints
- `app/api/config_routes.py` - Configuration
- `app/api/document_routes.py` - Document upload
- `app/api/metadata_routes.py` - Metadata generation
- Переместить бизнес-логику в `app/services/`

---

### 9. `app/services/cache/manager.py` - смешение инфраструктуры и бизнес-логики

**Файл:** `app/services/cache/manager.py`

**Проблема:**
Файл 434 строки, совмещает:

1. **Redis client управление**
2. **Cache CRUD операции**
3. **LRU eviction логика**
4. **Statistics computation** (должно быть в `stats.py`)
5. **Health checking**
6. **Global instance management** (singleton pattern)

**Последствия:**
- Нарушение SRP - класс делает слишком много
- Сложно тестировать отдельные части
- Смешение инфраструктуры (Redis) и бизнес-логики (eviction)

**Решение:**
Разделить на:
- `RedisCacheClient` - работа с Redis
- `CacheEvictionPolicy` - LRU логика
- `CacheManager` - координация (тонкий слой)
- `CacheHealthChecker` - мониторинг

---

### 10. `app/services/cache/session.py` - смешение доменов

**Файл:** `app/services/cache/session.py`

**Проблема:**
Файл управляет:

1. **User sessions** (Redis)
2. **Active session pointers**
3. **Session state updates** (read-modify-write)
4. **TTL management**

**Нарушение:**
- Смешение управления сессиями и состоянием диалога
- `dialog_state` не должен быть в session manager

**Решение:**
- Разделить на `SessionManager` (Redis CRUD) и `DialogStateManager` (бизнес-логика состояний)

---

### 11. `app/observability/state_validator.py` - смешение контрактов и валидации

**Файл:** `app/observability/state_validator.py`

**Проблема:**
Файл содержит:

1. **Определения контрактов** (`InputContract`, `OutputContract`)
2. **Валидацию** (`StateValidator.validate_input`, `validate_output`)
3. **Фильтрацию** (`filter_input`, `filter_output`)
4. **Default контракты** (`DefaultContracts`)

**Нарушение:**
- Валидация и фильтрация — разные ответственности
- Контракты могли быть отдельным модулем

**Решение:**
⏸️ **Отложено** - текущая организация файла достаточна для работы. Рефакторинг можно провести позже при необходимости.

---

### 12. `app/pipeline/config_proxy.py` - God Object антипаттерн

**Файл:** `app/pipeline/config_proxy.py`

**Проблема:**
`ConversationConfig` класс собирает параметры из разных нод:

```python
def aggregation_max_messages(self)
def use_llm_aggregation(self)
def use_llm_analysis(self)
def session_ttl_hours(self)
def max_attempts_before_escalation(self)
def escalation_confidence_threshold(self)
def clarification_enabled(self)
def always_escalate_categories(self)
def max_response_tokens(self)
```

**Нарушение:**
- Один класс знает о конфигах 5+ разных нод
- Нарушение SRP - каждая нода должна иметь свой config
- При добавлении новой ноды нужно менять этот класс (нарушение OCP)

**Решение:**
- Создать `app/services/config_loader/node_registry.py` с автоматической регистрацией нод
- Реализовать механизм:
  - Сканирование директории `app/nodes/` (исключая `base_node`, `_shared_config`)
  - Автоматическое обнаружение нод по наличию `config.yaml`
  - Сбор всех конфигов в единый объект
  - Добавление глобальных параметров из `_shared_config/global.yaml`
  - Поддержка enabled/disabled статуса для каждой ноды
- Каждая нода загружает свою конфигурацию через `get_node_config(node_name)`
- Удалить `config_proxy.py` после миграции всех импортов

**Пример структуры:**
```python
# app/services/config_loader/node_registry.py
class NodeRegistry:
    def __init__(self):
        self._nodes = self._discover_nodes()
    
    def _discover_nodes(self) -> Dict[str, NodeConfig]:
        """Автоматически находит все ноды в app/nodes/"""
        nodes = {}
        nodes_dir = Path("app/nodes")
        for node_path in nodes_dir.iterdir():
            if node_path.is_dir() and node_path.name not in ["base_node", "_shared_config"]:
                config_file = node_path / "config.yaml"
                if config_file.exists():
                    nodes[node_path.name] = self._load_node_config(node_path.name)
        return nodes
    
    def get_node_config(self, node_name: str) -> dict:
        """Получить конфиг конкретной ноды"""
        return self._nodes.get(node_name, {})
    
    def get_all_nodes(self) -> List[str]:
        """Получить список всех зарегистрированных нод"""
        return list(self._nodes.keys())
```

---

### 13. `app/storage/persistence.py` - смешение доменов

**Файл:** `app/storage/persistence.py`

**Проблема:**
`PersistenceManager` управляет:

1. **User profiles**
2. **Long-term memory**
3. **Sessions**
4. **Messages**
5. **Escalations**

**Нарушение:**
- Один класс управляет 5 разными доменами БД
- Изменение схемы любого домена требует изменения этого файла

**Решение:**
Разделить на:
- `UserRepository` - users, profiles
- `SessionRepository` - sessions
- `MessageRepository` - messages
- `EscalationRepository` - escalations

---

## 🟠 Смешанные ответственности и нечистые функции

### 14. `app/pipeline/graph.py` - side effects в graph building

**Файл:** `app/pipeline/graph.py`

**Проблема:**
```python
# Строки 201-202, 206, 211
print(f"DEBUG: Active config nodes: {active_node_names}")
print(f"DEBUG: Adding node {name}")
print(f"DEBUG: Warning: Node {name} enabled...")
```

**Нарушение:**
- Построение графа имеет сайд-эффекты (print)
- Смешение логирования и бизнес-логики
- Невозможно тестировать без вывода в консоль

**Решение:**
- Создать `app/observability/pipeline_logger.py` с единым классом для логирования
- Использовать `logging.debug()` вместо `print()`
- Отделить логирование от логики построения графа

**Пример структуры:**
```python
# app/observability/pipeline_logger.py
class PipelineLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(f"pipeline.{name}")
    
    def log_node_added(self, node_name: str):
        self.logger.debug(f"Adding node: {node_name}")
    
    def log_edge_added(self, from_node: str, to_node: str):
        self.logger.debug(f"Edge: {from_node} → {to_node}")
    
    def log_validation_result(self, result: bool, details: str):
        if result:
            self.logger.info(f"✓ Validation passed: {details}")
        else:
            self.logger.warning(f"✗ Validation failed: {details}")

# Использование в graph.py
pipeline_logger = PipelineLogger("graph_builder")
pipeline_logger.log_node_added(node_name)
```

---

### 15. `app/nodes/base_node/base_node.py` - смешение tracing и execution

**Файл:** `app/nodes/base_node/base_node.py`

**Проблема:**
`__call__` метод совмещает:

1. **Input filtering**
2. **Tracing setup** (Langfuse observe)
3. **Execution** (вызов `execute`)
4. **Output validation**
5. **Error handling**
6. **Logging**

**Нарушение:**
- Один метод делает слишком много
- Сложно тестировать отдельные части

**Решение:**
⏸️ **Отложено** - требует переписывания всех существующих нод. Планировать отдельно.

(Рефакторинг на отдельные методы приведет к необходимости обновления всех нод в системе. Оставить как есть до момента, когда будет выделено время на полный рефакторинг базовой ноды.)

---

### 16. `app/api/routes.py` - встроенная бизнес-логика в endpoints

**Файл:** `app/api/routes.py:500-505`

**Проблема:**
```python
# Построение classification pipeline прямо в endpoint
classifier = AutoClassificationPipeline(
    embedding_model="all-MiniLM-L6-v2",
    distance_threshold=0.7,
    confidence_threshold=0.65,
    llm_validation_threshold=0.4
)
```

**Нарушение:**
- Бизнес-логика встроена в API endpoint
- Невозможно переиспользовать логику
- Сложно тестировать отдельно от HTTP

**Решение:**
- Создать `app/services/metadata_analyzer.py`
- API вызывает сервис, а не создает объекты напрямую

---

## Рекомендации по приоритетам исправления

### 🔥 Критический приоритет (недели 1-2)

#### 1. Исправить зависимости storage/integrations → nodes
- **Задача:** Выделить переиспользуемые функции из нод в отдельные модули
- **Файлы:**
  - Создать `app/storage/vector_operations.py` (из `app/nodes/retrieval/storage.py`)
  - Создать `app/storage/lexical_operations.py` (из `app/nodes/lexical_search/storage.py`)
  - Создать `app/services/translation/translator.py` (из `app/nodes/query_translation/translator.py`)
  - Создать `app/services/classification/semantic_service.py` (из `app/nodes/easy_classification/semantic_classifier.py`)
- **Результат:** Ноды остаются на месте, но используют сервисы вместо прямого кода

#### 2. Разделить app/api/routes.py (725 строк)
- **Задача:** Создать отдельные роутеры по доменам
- **Новые файлы:**
  - `app/api/rag_routes.py` - `/search`, `/ask`, `/rag/query`
  - `app/api/config_routes.py` - `/config/*`
  - `app/api/document_routes.py` - `/documents/upload`, `/documents/confirm`
  - `app/api/metadata_routes.py` - `/documents/metadata-generation/*`
  - `app/api/main.py` - главный router с импортом всех под-роутеров
- **Результат:** Каждый домен в отдельном файле <200 строк

#### 3. Создать app/services/search.py для API
- **Задача:** API не должен напрямую вызывать ноды
- **Файл:** `app/services/search.py`
- **Методы:**
  - `async def search_documents(query, top_k)` - обертка для retrieval
  - `async def ask_question(question, hybrid)` - вызов rag_graph
- **Результат:** API вызывает только сервисы

### ⚠️ Высокий приоритет (недели 3-4)

#### 4. Разделить app/pipeline/graph.py (376 строк)
- **Задача:** Разбить на логические модули
- **Новые файлы:**
  - `app/pipeline/graph_builder.py` - основная логика построения графа
  - `app/pipeline/routing_logic.py` - функции маршрутизации (`cache_hit_logic`, `router_logic`, etc.)
  - `app/pipeline/validators.py` - `validate_pipeline_structure`
  - `app/pipeline/node_registry.py` - `NODE_FUNCTIONS`, импорты нод
- **Результат:** Каждый файл <150 строк, четкое разделение ответственностей

#### 5. Создать автоматическую регистрацию нод
- **Задача:** Заменить config_proxy.py на гибкий механизм
- **Файл:** `app/services/config_loader/node_registry.py`
- **Функционал:**
  - Автоматическое сканирование `app/nodes/` (кроме `base_node`, `_shared_config`)
  - Обнаружение нод по наличию `config.yaml`
  - Сбор конфигов в единый объект
  - Поддержка enabled/disabled статуса
  - API: `get_node_config(name)`, `get_all_nodes()`, `is_node_enabled(name)`
- **Удалить:** `app/pipeline/config_proxy.py`
- **Результат:** Добавление новой ноды не требует изменения кода регистрации

#### 6. Создать централизованного config_manager
- **Задача:** API не должен вызывать внутренние конфиги нод
- **Файл:** `app/services/config_manager.py`
- **Методы:**
  - `clear_all_caches()` - очистка всех кешей
  - `reload_configs()` - перезагрузка конфигураций
  - `get_system_config()` - получение системных настроек
- **Результат:** Единая точка входа для управления конфигами

#### 7. Создать PipelineLogger
- **Задача:** Убрать print() из graph.py
- **Файл:** `app/observability/pipeline_logger.py`
- **Методы:**
  - `log_node_added(node_name)`
  - `log_edge_added(from, to)`
  - `log_validation_result(result, details)`
- **Результат:** Структурированное логирование с уровнями

### 📋 Средний приоритет (недели 5-6)

#### 8. Разделить CacheManager (434 строки)
- **Задача:** Разделить на компоненты
- **Новые файлы:**
  - `app/services/cache/redis_client.py` - работа с Redis
  - `app/services/cache/eviction_policy.py` - LRU логика
  - `app/services/cache/health_checker.py` - мониторинг
  - `app/services/cache/manager.py` - координация (тонкий слой)
- **Результат:** Каждый компонент можно тестировать отдельно

#### 9. Разделить PersistenceManager
- **Задача:** Разделить по доменам БД
- **Новые файлы:**
  - `app/storage/repositories/user_repository.py` - users, profiles
  - `app/storage/repositories/session_repository.py` - sessions
  - `app/storage/repositories/message_repository.py` - messages
  - `app/storage/repositories/escalation_repository.py` - escalations
- **Результат:** Изменение одной таблицы не затрагивает другие

#### 10. Разделить SessionManager
- **Задача:** Разделить Redis CRUD и бизнес-логику
- **Новые файлы:**
  - `app/services/cache/session_manager.py` - Redis CRUD для сессий
  - `app/services/dialog/state_manager.py` - управление состоянием диалога
- **Результат:** Четкое разделение инфраструктуры и логики

#### 11. Переместить conversation_config
- **Задача:** Убрать зависимость services → pipeline
- **Файл:** Переместить в `app/services/config_loader/conversation_config.py`
- **Обновить импорты:** В `session.py` и других файлах
- **Результат:** Правильное направление зависимостей

### 🔧 Низкий приоритет / Отложенные

#### 12. Metadata analyzer сервис
- **Задача:** Убрать бизнес-логику из API endpoints
- **Файл:** `app/services/metadata_analyzer.py`
- **Результат:** Логика metadata generation переиспользуется

#### 13. ⏸️ Рефакторинг BaseNode (ОТЛОЖЕНО)
- **Причина:** Требует переписывания всех существующих нод
- **Когда:** После стабилизации архитектуры, отдельный sprint

#### 14. ⏸️ Разделение state_validator.py (ОТЛОЖЕНО)
- **Причина:** Текущая организация достаточна
- **Когда:** При необходимости расширения функционала

---

## Дополнительные задачи

### Создать базовые утилиты

#### app/services/search.py
```python
"""Search service for API layer"""
from app.integrations.embeddings import get_embedding
from app.storage.vector_operations import vector_search
from app.storage.lexical_operations import lexical_search

async def search_documents(query: str, top_k: int = 3):
    """Unified search interface"""
    emb = await get_embedding(query)
    results = await vector_search(emb, top_k)
    return results
```

#### app/services/config_manager.py
```python
"""Centralized configuration management"""
from app.services.config_loader.loader import clear_config_cache
from app.nodes._shared_config.history_filter import clear_filter_cache

class ConfigManager:
    @staticmethod
    async def clear_all_caches():
        """Clear all configuration caches"""
        clear_config_cache()
        clear_filter_cache()
        return {"status": "ok", "message": "All caches cleared"}
    
    @staticmethod
    def reload_configs():
        """Reload all configurations"""
        return ConfigManager.clear_all_caches()
```

---

---

## Метрики текущего состояния

| Метрика | Значение | Целевое |
|---------|----------|---------|
| Нарушений зависимостей | 6 | 0 |
| Нарушений SRP | 7 | 0 |
| Файлов >400 строк | 3 | 0 |
| Circular imports риск | Высокий | Низкий |
| Уровень связности | Высокий | Низкий |

---

## Архитектурные принципы для следования

1. **Dependency Rule**: Зависимости всегда направлены к центру (nodes → services → storage)
2. **Single Responsibility**: Один файл/класс = одна зона ответственности
3. **Open/Closed**: Расширение через наследование/конфигурацию, а не модификацию
4. **Dependency Inversion**: Зависимость от абстракций, а не конкретных реализаций
5. **Interface Segregation**: Много маленьких интерфейсов лучше одного большого

---

**Отчет подготовлен:** Automatische Analyse  
**Следующий аудит:** После исправления критических нарушений
