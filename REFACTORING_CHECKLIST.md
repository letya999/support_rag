# 📋 Архитектурный рефакторинг - Чеклист выполнения

> **Обновлено:** 2026-01-09  
> **Статус:** 14 из 16 задач выполнено

---

## 🔥 Неделя 1-2: Критические зависимости

### ✅ Задача 1: Выделить storage функции из nodes

> **Приоритет:** 🔴 Критический  
> **Время:** 4-6 часов  
> **Статус:** ✅ Сделано

**Что делать:**

1. Создать `app/storage/vector_operations.py`
   - [x] Переместить функции из `app/nodes/retrieval/storage.py`
   - [x] Оставить в nodes только node-специфичную логику
   - [x] Экспортировать: `vector_search(embedding, top_k)`

2. Создать `app/storage/lexical_operations.py`
   - [x] Переместить из `app/nodes/lexical_search/storage.py`
   - [x] Экспортировать: `lexical_search_db(query, top_k)`

3. Обновить `app/storage/vector_store.py`
   ```python
   # Вместо:
   from app.nodes.retrieval.storage import vector_search
   # Написать:
   from app.storage.vector_operations import vector_search
   ```

4. Обновить импорты в нодах
   - [x] `app/nodes/retrieval/node.py` → импорт из `app.storage`
   - [x] `app/nodes/lexical_search/node.py` → импорт из `app.storage`

**Проверка:**
```bash
# Не должно быть импортов app.nodes в app.storage
grep -r "from app.nodes" app/storage/
```

---

### ✅ Задача 2: Выделить translator в сервис

> **Приоритет:** 🔴 Критический  
> **Время:** 2-3 часа  
> **Статус:** ✅ Сделано

**Что делать:**

1. Создать `app/services/translation/`
   - [x] `__init__.py`
   - [x] `translator.py` - переместить из `app/nodes/query_translation/translator.py`

2. Обновить импорты
   - [x] `app/nodes/query_translation/node.py`
   - [x] `app/integrations/translation.py`

**Код для обновления:**
```python
# В app/integrations/translation.py
from app.services.translation.translator import translator

# В app/nodes/query_translation/node.py
from app.services.translation.translator import translator
```

---

### ✅ Задача 3: Выделить SemanticClassificationService

> **Приоритет:** 🔴 Критический  
> **Время:** 2-3 часа  
> **Статус:** ✅ Сделано

**Что делать:**

1. Создать `app/services/classification/`
   - [x] `__init__.py`
   - [x] `semantic_service.py` - переместить из `app/nodes/easy_classification/semantic_classifier.py`

2. Обновить импорты
   - [x] `app/nodes/easy_classification/node.py`
   - [x] `app/services/metadata_generation/embedding_classifier.py`

---

### ✅ Задача 4: Разделить app/api/routes.py

> **Приоритет:** 🔴 Критический  
> **Время:** 6-8 часов  
> **Статус:** ✅ Сделано

**Что делать:**

1. Создать структуру роутеров
   ```
   app/api/
   ├── __init__.py (обновить)
   ├── main.py (новый - главный роутер)
   ├── rag_routes.py (новый)
   ├── config_routes.py (новый)
   ├── document_routes.py (новый)
   └── metadata_routes.py (новый)
   ```

2. Перенести endpoints
   - [x] **rag_routes.py** - `/search`, `/ask`, `/rag/query`, `/health`
   - [x] **config_routes.py** - `/config/system-phrases`, `/config/languages`, `/config/reload`
   - [x] **document_routes.py** - `/documents/upload`, `/documents/confirm`
   - [x] **metadata_routes.py** - `/documents/metadata-generation/*`

3. Создать главный роутер
   ```python
   # app/api/main.py
   from fastapi import APIRouter
   from . import rag_routes, config_routes, document_routes, metadata_routes
   
   router = APIRouter()
   router.include_router(rag_routes.router, tags=["RAG"])
   router.include_router(config_routes.router, prefix="/config", tags=["Config"])
   router.include_router(document_routes.router, prefix="/documents", tags=["Documents"])
   router.include_router(metadata_routes.router, prefix="/documents/metadata-generation", tags=["Metadata"])
   ```

4. Переименовать старый файл
   - [x] `routes.py` → `routes_old.py` (для резервной копии)

**Проверка:**
- [x] Каждый новый файл <200 строк
- [x] Все endpoints работают
- [x] Импорты обновлены в main приложении

---

### ✅ Задача 5: Создать app/services/search.py

> **Приоритет:** 🔴 Критический  
> **Время:** 1-2 часа  
> **Статус:** ✅ Сделано

**Что делать:**

1. Создать `app/services/search.py`
   ```python
   """Search service for API layer - abstracts retrieval nodes"""
   from typing import List, Dict, Any
   from app.integrations.embeddings import get_embedding
   from app.storage.vector_operations import vector_search
   from app.storage.lexical_operations import lexical_search_db
   
   async def search_documents(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
       """Vector search through storage layer"""
       emb = await get_embedding(query)
       results = await vector_search(emb, top_k)
       return [
           {
               "content": r.content,
               "score": r.score,
               "metadata": r.metadata
           }
           for r in results
       ]
   ```

2. Обновить `app/api/rag_routes.py`
   - [x] Заменить прямой вызов `retrieve_context` на `search_documents`

---

### ✅ Задача 6: Создать app/services/config_manager.py

> **Приоритет:** 🔴 Критический  
> **Время:** 1 час  
> **Статус:** ✅ Сделано

**Что делать:**

1. Создать `app/services/config_manager.py`
   ```python
   """Centralized configuration management"""
   from app.services.config_loader.loader import clear_config_cache
   from app.nodes._shared_config.history_filter import clear_filter_cache
   
   class ConfigManager:
       @staticmethod
       async def clear_all_caches() -> dict:
           """Clear all configuration caches"""
           clear_config_cache()
           clear_filter_cache()
           return {"status": "ok", "message": "All caches cleared"}
       
       @staticmethod
       async def reload_configs() -> dict:
           """Reload all configurations"""
           return await ConfigManager.clear_all_caches()
   ```

2. Обновить `app/api/config_routes.py`
   - [x] Заменить прямые вызовы на `ConfigManager.reload_configs()`

---

## ⚠️ Неделя 3-4: Модульность pipeline

### ✅ Задача 7: Разделить app/pipeline/graph.py

> **Приоритет:** ⚠️ Высокий  
> **Время:** 8-10 часов  
> **Статус:** ✅ Сделано

**Что делать:**

1. Создать структуру
   ```
   app/pipeline/
   ├── graph.py (обновить - главный файл, только compile)
   ├── graph_builder.py (новый)
   ├── routing_logic.py (новый)
   ├── validators.py (новый)
   ├── node_registry.py (новый)
   ```

2. **node_registry.py** - регистрация нод
   - [x] Переместить `NODE_FUNCTIONS` словарь
   - [x] Переместить импорты всех нод

3. **routing_logic.py** - функции маршрутизации
   - [x] `cache_hit_logic(state)`
   - [x] `router_logic(state)`
   - [x] `should_fast_escalate(state)`
   - [x] `check_guardrails_outcome(state)`

4. **validators.py** - валидация
   - [x] `validate_pipeline_structure(active_nodes)`

5. **graph_builder.py** - построение графа
   - [x] Основная логика добавления нод и ребер
   - [x] Использует функции из других модулей

6. **graph.py** - точка входа
   ```python
   from app.pipeline.graph_builder import build_graph
   
   rag_graph = build_graph()
   ```

**Проверка:**
- [x] Каждый файл <150 строк
- [x] Pipeline работает как раньше
- [x] Импорты обновлены

---

### ✅ Задача 8: NodeRegistry с автообнаружением

> **Приоритет:** ⚠️ Высокий  
> **Время:** 6-8 часов  
> **Статус:** ✅ Сделано

**Что делать:**

1. Создать `app/services/config_loader/node_registry.py`
   ```python
   from pathlib import Path
   from typing import Dict, List
   import yaml
   
   class NodeRegistry:
       EXCLUDED_DIRS = ["base_node", "_shared_config", "__pycache__"]
       
       def __init__(self, nodes_dir: str = "app/nodes"):
           self.nodes_dir = Path(nodes_dir)
           self._nodes = self._discover_nodes()
       
       def _discover_nodes(self) -> Dict[str, dict]:
           """Auto-discover all nodes in app/nodes/"""
           nodes = {}
           for node_path in self.nodes_dir.iterdir():
               if not node_path.is_dir():
                   continue
               if node_path.name in self.EXCLUDED_DIRS:
                   continue
               
               config_file = node_path / "config.yaml"
               if config_file.exists():
                   with open(config_file) as f:
                       config = yaml.safe_load(f)
                       nodes[node_path.name] = config
           return nodes
       
       def get_node_config(self, node_name: str) -> dict:
           return self._nodes.get(node_name, {})
       
       def get_all_nodes(self) -> List[str]:
           return list(self._nodes.keys())
       
       def is_node_enabled(self, node_name: str) -> bool:
           config = self.get_node_config(node_name)
           return config.get("enabled", False)
   ```

2. Обновить `app/services/config_loader/loader.py`
   - [x] Использовать `NodeRegistry` вместо хардкода

3. Удалить `app/pipeline/config_proxy.py`
   - [x] Найти все импорты: `grep -r "config_proxy" app/`
   - [x] Заменить на `NodeRegistry`

---

### ✅ Задача 9: PipelineLogger

> **Приоритет:** ⚠️ Высокий  
> **Время:** 2-3 часа  
> **Статус:** ✅ Сделано

**Что делать:**

1. Создать `app/observability/pipeline_logger.py`
   ```python
   import logging
   
   class PipelineLogger:
       def __init__(self, name: str):
           self.logger = logging.getLogger(f"pipeline.{name}")
       
       def log_node_added(self, node_name: str):
           self.logger.debug(f"✓ Node added: {node_name}")
       
       def log_edge_added(self, from_node: str, to_node: str):
           self.logger.debug(f"✓ Edge: {from_node} → {to_node}")
       
       def log_validation_result(self, success: bool, message: str):
           if success:
               self.logger.info(f"✓ {message}")
           else:
               self.logger.warning(f"✗ {message}")
       
       def log_config_loaded(self, node_count: int):
           self.logger.info(f"Loaded {node_count} nodes from config")
   ```

2. Обновить `app/pipeline/graph_builder.py`
   - [x] Заменить все `print()` на `pipeline_logger.log_*()`

---

### ✅ Задача 10: Переместить conversation_config

> **Приоритет:** ⚠️ Высокий  
> **Время:** 1 час  
> **Статус:** ✅ Сделано

**Что делать:**

1. Переместить файл
   - [x] `app/pipeline/config_proxy.py` → `app/services/config_loader/conversation_config.py`

2. Обновить импорты
   - [x] `app/services/cache/session.py`
   - [x] Все другие места: `grep -r "config_proxy" app/`

---

## 📋 Неделя 5-6: Рефакторинг сервисов

### ✅ Задача 11: Разделить CacheManager

> **Приоритет:** 📋 Средний  
> **Время:** 8-10 часов  
> **Статус:** ✅ Сделано

**Структура:**
```
app/services/cache/
├── manager.py (координация)
├── redis_client.py (Redis операции)
├── eviction_policy.py (LRU логика)
└── health_checker.py (мониторинг)
```

---

### ✅ Задача 12: Разделить PersistenceManager

> **Приоритет:** 📋 Средний  
> **Время:** 10-12 часов  
> **Статус:** ✅ Сделано

**Структура:**
```
app/storage/repositories/
├── __init__.py
├── user_repository.py
├── session_repository.py
├── message_repository.py
└── escalation_repository.py
```

---

### ✅ Задача 13: Разделить SessionManager

> **Приоритет:** 📋 Средний  
> **Время:** 4-6 часов  
> **Статус:** ✅ Сделано

**Файлы:**
- `app/services/cache/session_manager.py` - Redis CRUD
- `app/services/dialog/state_manager.py` - бизнес-логика состояний

---

### ✅ Задача 14: Metadata analyzer сервис

> **Приоритет:** 🔧 Низкий  
> **Время:** 3-4 часа  
> **Статус:** ✅ Сделано

**Файл:** `app/services/metadata_analyzer.py`

---

## ⏸️ Отложенные задачи

### Задача 15: Рефакторинг BaseNode
**Статус:** ⏸️ Отложено  
**Причина:** Требует переписывания всех нод  
**Когда:** После стабилизации

### Задача 16: Разделение state_validator.py
**Статус:** ⏸️ Отложено  
**Причина:** Работает достаточно хорошо  
**Когда:** При необходимости расширения

---

> **Статус:** 14 из 14 задач выполнено

## 📊 Прогресс

```
Неделя 1-2: [x] [x] [x] [x] [x] [x]     6/6  (100%)
Неделя 3-4: [x] [x] [x] [x]             4/4  (100%)
Неделя 5-6: [x] [x] [x] [x]             4/4  (100%)
Отложено:   [⏸️] [⏸️]                      0/2  (н/д)
─────────────────────────────────────────────
ИТОГО:                                  14/14 (100%)
```

---

## 🚀 Как начать

1. **Создайте ветку:**
   ```bash
   git checkout -b refactor/architecture-cleanup
   ```

2. **Начните с Quick Wins (Задачи 1-3)**
   - Быстрый результат за 1-2 дня
   - Исправляет критические зависимости

3. **После каждой задачи:**
   - Запустите тесты
   - Обновите чеклист
   - Коммит с описанием

4. **Регулярные проверки:**
   ```bash
   # Проверка зависимостей
   grep -r "from app.nodes" app/storage app/services app/integrations
   
   # Подсчет строк в файлах
   wc -l app/api/*.py app/pipeline/*.py
   ```

---

**Следующий шаг:** [Задача 14: Metadata analyzer сервис](#-задача-14-metadata-analyzer-сервис)
