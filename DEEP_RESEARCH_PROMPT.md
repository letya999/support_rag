# Промпт для Deep Research: State Pollution & Node Contract Validation в LangGraph

## 🎯 ОСНОВНАЯ ПРОБЛЕМА

В production LangGraph RAG pipeline (Support RAG с 24 узлами) наблюдаются 2 критические проблемы observability:

### Problem 1: State Pollution
**Суть:** Каждый узел в графе получает ПОЛНЫЙ state целиком (18KB-30KB) вместо только требуемых полей.

**Текущее поведение:**
```
session_starter (вход): 218 bytes → output: 5 полей ✅
check_cache (вход): 18,839 bytes → нужно только question (50 bytes) ❌
routing (вход): 29,621 bytes → нужно только answer + confidence (200 bytes) ❌
store_in_cache (вход): 29,984 bytes → нужно только question + answer + cache_key ❌
```

**Почему это проблема:**
- Логи Langfuse содержат 10KB+ ненужных данных
- conversation_history и docs повторяются на входе каждого узла
- Трудно отследить реальные входы/выходы узла
- Неэффективно с точки зрения пропускной способности и стоимости

### Problem 2: State Bloat
**Суть:** Узлы возвращают весь state целиком (53+ поля) вместо только своих изменений.

**Текущее поведение:**
```
session_starter.execute() returns: {"conversation_history", "user_profile", ...} (5 полей) ✅
telegram_rag_query.execute() returns: {весь state из 53 полей} ❌
store_in_cache.execute() returns: {весь state из 53 полей} ❌
```

---

## 🏗️ ТЕКУЩИЙ СЕТАП КОДОВОЙ БАЗЫ

### Архитектура:
- **Framework:** LangGraph (latest 0.x версия)
- **LLM Framework:** LangChain (latest версия)
- **Observability:** Langfuse 3.11.2+
- **Language:** Python
- **State Management:** TypedDict-based state из `app/pipeline/state.py`

### Структура узлов:
```
app/nodes/
├── base_node/base_node.py         # Абстрактный базовый класс для всех узлов
├── session_starter/node.py        # Загрузка session (правильно: 5 выходных полей)
├── input_guardrails/node.py       # Валидация входа
├── check_cache/nodes.py           # Проверка кэша
├── hybrid_search/node.py          # Поиск документов
├── generation/node.py             # Генерация ответа
├── routing/node.py                # Маршрутизация действия
├── store_in_cache/nodes.py        # Сохранение в кэш
└── ... (18 других узлов)

app/pipeline/
├── state.py                       # TypedDict State (100+ полей)
├── graph.py                       # StateGraph определение
└── config_proxy.py                # Конфиги для узлов
```

### Observability Setup:
- Langfuse @observe декораторы на функциях
- langfuse_context.update_current_observation() для логирования в BaseNode.__call__
- Автоматический capture args/kwargs (ПРОБЛЕМА: логирует весь state)

---

## 🔍 ЧТО НУЖНО ИССЛЕДОВАТЬ

### 1. В официальной документации LangGraph

**GitHub repos:**
- `langchain-ai/langgraph` - основной репозиторий
  - Ищите: примеры с input_schema, output_schema, reducers
  - Версия: v0.1.x+ (2024-2025)
  - Ищите: как фильтруются входные данные на уровне StateGraph

**Ключевые файлы для изучения:**
- `graph.py` - как StateGraph обрабатывает state
- `pregel.py` - как выполняются узлы (может быть здесь есть hook для фильтрации)
- `errors.py` и тесты - edge cases

**Вопросы к ответам:**
- Существует ли native способ передать узлу только часть state?
- Может ли reducer функция отфильтровать входные данные перед передачей в узел?
- Есть ли конфигурация на уровне узла (add_node) для фильтрации inputs?

### 2. In Official LangChain Documentation

**GitHub:**
- `langchain-ai/langchain` - основной репозиторий
- Ищите: Runnable, invoke, stream APIs
- Ищите: как работает .invoke() с input_schema

**Ключевые концепции для исследования:**
- Runnable.with_config() - может ли быть использован для фильтрации?
- Runnable.with_types() - типизация входов
- Tool validation - как инструменты валидируют входы?
- @chain декоратор - может ли использоваться для фильтрации?

**Вопросы:**
- Можно ли создать Runnable wrapper который фильтрует state?
- Как LangChain инструменты ограничивают свои входы?

### 3. В Langfuse документации и GitHub

**GitHub:**
- `langfuse/langfuse` - основной репозиторий
- `langfuse/langfuse-python` - Python SDK

**Ищите:**
- Как отключить auto-capture args/kwargs (найдено: capture_input=False)
- Как явно передавать input/output в @observe
- Взаимодействие с LangGraph nodes
- Есть ли built-in интеграция для фильтрации state в наблюдение?

**Вопросы:**
- Может ли Langfuse SDK перехватить передачу state в узел?
- Есть ли хук для логирования отфильтрованного state вместо полного?

### 4. В примерах и cookbook'ах

**Ищите на:**
- https://github.com/langchain-ai/langgraph/tree/main/examples
- https://github.com/langchain-ai/langchain/tree/master/cookbook
- https://langfuse.com/guides/cookbook
- Medium статьи от авторов LangGraph/LangChain

**Ищите специфически:**
- "state filtering" + LangGraph
- "reduce state" + LangGraph
- "input validation" + LangGraph nodes
- "observability best practices" + agents
- Примеры с большим числом узлов (15+)
- Примеры с complex state management

### 5. GitHub Issues & Discussions

**LangGraph Issues/Discussions:**
- Поищите: "state pollution"
- Поищите: "input filtering"
- Поищите: "reduce state size"
- Поищите: "node receives full state"
- Поищите: "StateGraph input schema"
- Ключевой вопрос: есть ли открытые issue про то что узлы получают весь state?

**LangChain Issues:**
- Поищите: "node input validation"
- Поищите: "tool input filtering"

**Langfuse Issues:**
- Поищите: "state capture", "large state", "input logging"

### 6. Статьи и Blog Posts (Medium, Dev.to, etc)

**Ищите статьи с названиями типа:**
- "LangGraph Advanced State Management 2025"
- "Optimizing LangGraph Performance: State Size"
- "Best Practices for LangGraph Observable Pipelines"
- "State Management Patterns in LangGraph"
- "Reducing State Complexity in Agentic Workflows"

**Авторы для внимания:**
- Harrison Chase (LangChain creator)
- Лидеры LangGraph team
- Popular LLM engineers на Medium (те кто пишут про production systems)

---

## 🎯 ВАЖНЫЕ НЮАНСЫ И EDGE CASES

### Нюанс 1: LangGraph версия имеет значение
- В v0.0.x state management работает одним способом
- В v0.1.x+ появилась улучшенная поддержка input/output schemas
- **Уточните:** Какие версии LangGraph поддерживают input_schema фильтрацию на уровне node.add_node()?

### Нюанс 2: Reducer функции работают только на выходе узла
- Reducer вызывается ПОСЛЕ узла возвращает данные (для обновления state)
- Они НЕ фильтруют ЧТО передается узлу, только КАК результат мержится в state
- **Важно:** Нужно искать что-то ДРУГОЕ для фильтрации входа

### Нюанс 3: BaseNode.__call__ vs execute
- `__call__` вызывается LangGraph - здесь есть доступ к full state
- `execute` это abstract метод который переопределяется в подклассах
- **Вопрос:** Можно ли в `__call__` фильтровать state перед передачей в execute?

### Нюанс 4: Observability와 Filtering
- Langfuse capture происходит в момент вызова функции (@observe декоратор)
- Если отключить capture_input, то ничего не логируется
- Нужно явно передавать отфильтрованные данные через langfuse_context
- **Вопрос:** Какой правильный паттерн для logирования отфильтрованного input?

### Нюанс 5: TypedDict state и type hints
- Если state определена как TypedDict с 100+ полями, это не означает что все передаются в узел
- **Важно:** Проверить как Python/LangGraph обрабатывают типы
- Может быть есть способ ограничить TypedDict для узла?

### Нюанс 6: Асинхронность
- Все узлы async (async def execute)
- Фильтрация должна быть async-compatible
- **Искать:** async примеры фильтрации state

### Нюанс 7: Recursive State
- У вас conversation_history это список, docs это список
- Они растут со временем
- **Важно:** Как обычно обрезают/архивируют recursive данные в LangGraph?
- Ищите: RemoveMessage паттерн, summarization

### Нюанс 8: Private State в LangGraph
- Есть концепция "private state" которая не экспортируется на выход
- Может быть это решает проблему State Bloat для служебных полей?
- **Ищите:** Как определить private поле в state?

---

## 📝 ПЛАН ИССЛЕДОВАНИЯ

### Phase 1: Foundation (1-2 часа)
1. Изучить LangGraph source code - как именно state передается в узел
2. Проверить `graph.py` как вызывается узел (invoke, batch, stream)
3. Найти точку где можно перехватить и отфильтровать state

### Phase 2: Patterns (2-3 часа)
1. Собрать все примеры с input_schema + output_schema
2. Найти примеры с reducers которые фильтруют
3. Найти примеры с private state

### Phase 3: Solutions (2-3 часа)
1. Исследовать существующие solutions в GitHub
2. Найти какие проекты решали похожую проблему
3. Определить какой подход лучше всего подходит для вашего use case

### Phase 4: Observability (1-2 часа)
1. Как правильно логировать отфильтрованный state в Langfuse
2. Какой паттерн использовать для @observe
3. Как логировать в langfuse_context

---

## 🔑 КЛЮЧЕВЫЕ ПОИСКОВЫЕ ЗАПРОСЫ

### GitHub поиск:
```
repo:langchain-ai/langgraph "input_schema" node
repo:langchain-ai/langgraph state filter
repo:langchain-ai/langgraph "StateGraph" reduce
repo:langchain-ai/langgraph reduce input
site:github.com langgraph "node receives" state
site:github.com langgraph state pollution
```

### Google/статьи поиск:
```
"LangGraph" "state filtering" best practices
"LangGraph" reduce state size
"LangGraph" input validation node
LangGraph observability "full state"
LangGraph reducers filtering
```

### Stack Overflow / Discussions:
```
site:stackoverflow.com langgraph state filter
site:github.com/langchain-ai/langgraph discussions state
site:reddit.com/r/LLMs langgraph state management
```

---

## 📋 CHECKPOINTS ДЛЯ ПРОВЕРКИ

**После исследования ответьте на эти вопросы:**

1. ✅ Есть ли native способ в LangGraph v0.x чтобы узел получал только часть state?
2. ✅ Как именно работает input_schema фильтрация на входе StateGraph.invoke()?
3. ✅ Можно ли применить input_schema фильтрацию на уровне отдельного узла (add_node)?
4. ✅ Как правильно использовать reducers для фильтрации state?
5. ✅ Что такое "private state" в LangGraph и решает ли это State Bloat?
6. ✅ Какой паттерн используется в production системах для observability с большим state?
7. ✅ Как Langfuse работает с filtered/partial state?
8. ✅ Есть ли существующие библиотеки/middleware для state filtering в LangGraph?
9. ✅ Какие у есть edge cases и gotchas которых нужно избежать?
10. ✅ Какой подход выбрать: LangGraph-native vs custom wrapper vs middleware декоратор?

---

## 💡 КОНТЕКСТ ДЛЯ ПОИСКА

**Версии в вашем проекте:**
- LangGraph: v0.x (latest)
- LangChain: v0.2.x+ (latest)
- Langfuse: 3.11.2+

**Размеры проблемы:**
- 24 узла в графе
- State с 100+ полями
- Input size растет от 218b (session_starter) до 30KB (store_in_cache)
- Каждый запрос = 10-30KB ненужных данных в логах

**Performance Impact:**
- Langfuse API calls с 10x larger payload
- Сложнее отладить issues
- Трудно анализировать логи вручную

---

## 🎓 РЕЗУЛЬТАТ ИССЛЕДОВАНИЯ

В конце должен получиться документ типа:

```
## Deep Research Results: State Management in LangGraph

### Finding 1: How State is Passed to Nodes
[Объяснение как именно работает]

### Finding 2: Native Filtering Mechanisms
[Что LangGraph предоставляет из коробки]

### Finding 3: Recommended Patterns
[Какие паттерны используются в production]

### Finding 4: Implementation Strategy
[Какой подход выбрать и почему]

### Finding 5: Observability Best Practices
[Как правильно логировать filtered state]

### Conclusion & Recommendation
[Финальная рекомендация для вашего плана]
```

