# Рекомендации по улучшению архитектуры узлов

## Обзор

На основе анализа выявлены области, где архитектура может быть **укреплена** для повышения гибкости и надежности без нарушения существующего функционала.

---

## 1. КРИТИЧЕСКАЯ ПРОБЛЕМА: Fusion требует обе функции поиска

### 📋 Описание проблемы

**Файл:** `/app/nodes/fusion/node.py:11-12`

```python
vector_results = state.get("vector_results", [])
lexical_results = state.get("lexical_results", [])
```

Если в pipeline используются:
- ✅ Только `hybrid_search` - OK (hybrid делает оба поиска)
- ✅ `retrieve` + `lexical_search` + `fusion` - OK (обе функции есть)
- ❌ Только `retrieve` без `lexical_search` + `fusion` - ошибка (fusion вернет [])
- ❌ Только `lexical_search` без `retrieve` + `fusion` - ошибка (fusion вернет [])

### 🎯 Решение

**Вариант 1: Валидация (рекомендуется)**

```python
# /app/nodes/fusion/node.py
class FusionNode(BaseNode):
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        vector_results = state.get("vector_results", [])
        lexical_results = state.get("lexical_results", [])

        # Валидация: оба результата должны присутствовать
        if not vector_results or not lexical_results:
            raise ValueError(
                f"Fusion требует обе функции поиска: "
                f"vector_results={len(vector_results)}, "
                f"lexical_results={len(lexical_results)}"
            )

        # ... rest of code
```

**Вариант 2: Graceful degradation**

```python
class FusionNode(BaseNode):
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        vector_results = state.get("vector_results", [])
        lexical_results = state.get("lexical_results", [])

        # Если только один результат, использовать его
        if not vector_results and lexical_results:
            return {
                "docs": [r.content for r in lexical_results],
                "scores": [r.score for r in lexical_results],
                "confidence": lexical_results[0].score if lexical_results else 0.0
            }

        if not lexical_results and vector_results:
            return {
                "docs": [r.content for r in vector_results],
                "scores": [r.score for r in vector_results],
                "confidence": vector_results[0].score if vector_results else 0.0
            }

        # Оба есть - нормальная fusion
        fused_results = reciprocal_rank_fusion(vector_results, lexical_results)
        ...
```

**Вариант 3: Условное выполнение в graph.py**

```python
# /app/pipeline/graph.py
# Если используется fusion, обе функции поиска должны быть включены
if "fusion" in active_node_names:
    required_search_methods = ["retrieve", "lexical_search"]
    missing = [m for m in required_search_methods if m not in active_node_names]

    if missing:
        raise ValueError(
            f"Fusion требует обе функции поиска, "
            f"но отсутствуют: {missing}. "
            f"Используйте 'hybrid_search' или включите обе функции."
        )
```

### ✅ Рекомендуемое решение

**Вариант 1 + Документация в `pipeline_order.yaml`:**

```yaml
# /app/pipeline/pipeline_order.yaml
pipeline_order:
  # ... other nodes ...

  # ВАЖНО: Выберите ОДИН из подходов поиска:
  # Вариант A: Гибридный поиск (рекомендуется)
  - hybrid_search

  # Вариант B: Разделенный поиск (требует fusion)
  # Если используете fusion, ОБА узла должны быть включены:
  # - retrieve
  # - lexical_search
  # - fusion
```

---

## 2. ПРОБЛЕМА: Множественные переписи поля `docs`

### 📋 Описание проблемы

Поле `docs` переписывается несколькими узлами подряд:

```
retrieve
  → docs = [vector results]
hybrid_search
  → docs = [hybrid results]
retrieve + lexical_search + fusion
  → docs = [retrieve results]
  → docs = [lexical results]
  → docs = [fused results]
reranking
  → docs = [reranked results]
multihop
  → docs = [multihop results]
```

Это затрудняет отладку и может привести к потере информации.

### 🎯 Решение

**Использовать отдельные поля для каждого этапа:**

```python
# /app/pipeline/state.py - Добавить новые поля
class State(TypedDict):
    # Текущие поля (переписываются)
    docs: Annotated[List[str], keep_latest]

    # НОВЫЕ: Сохранять результаты каждого узла
    vector_search_results: Annotated[Optional[List[str]], overwrite]
    lexical_search_results: Annotated[Optional[List[str]], overwrite]
    retrieved_docs_initial: Annotated[Optional[List[str]], overwrite]
    docs_after_reranking: Annotated[Optional[List[str]], overwrite]
    docs_after_multihop: Annotated[Optional[List[str]], overwrite]
```

**Альтернатива: Структурированная история**

```python
# /app/pipeline/state.py
class SearchAudit(TypedDict):
    initial: List[str]
    after_reranking: List[str]
    after_multihop: List[str]
    timestamps: List[str]

class State(TypedDict):
    docs: Annotated[List[str], keep_latest]
    search_audit: Annotated[Optional[SearchAudit], overwrite]
```

### ✅ Рекомендуемое решение

**Минимальное вмешательство: Логирование**

```python
# /app/nodes/base_node/base_node.py
class BaseNode(ABC):
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Логировать docs перед и после
        docs_before = state.get("docs", [])

        result = await self.execute(state)

        docs_after = result.get("docs", docs_before)

        if docs_before != docs_after:
            print(f"[{self.name}] docs changed: {len(docs_before)} → {len(docs_after)}")

        return result
```

---

## 3. ПРОБЛЕМА: State Machine требует поле `confidence`

### 📋 Описание проблемы

`state_machine` использует `confidence` для принятия решений:

**Файл:** `/app/nodes/state_machine/node.py`

```python
confidence = state.get("confidence", 0.0)
# ... использует confidence в rules ...
```

Но если узлы переупорядочены, `confidence` может быть рассчитана раньше или позже.

### 🎯 Решение

**Сделать поле полностью опциональным с fallback:**

```python
# /app/nodes/state_machine/node.py
class StateMachineNode(BaseNode):
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        analysis = state.get("dialog_analysis", {})
        current_state = state.get("dialog_state") or INITIAL
        attempt_count = state.get("attempt_count") or 0

        # Получить confidence, но это опционально
        confidence = state.get("confidence")

        # Если confidence не установлена, пропустить правила,
        # зависящие от нее
        if confidence is None:
            print("⚠️ state_machine: confidence не установлена, "
                  "используются только dialog_analysis сигналы")

        # Правила, независящие от confidence
        if analysis.get(SIGNAL_SAFETY_VIOLATION):
            return {
                "dialog_state": SAFETY_VIOLATION,
                "action_recommendation": "block",
                # ...
            }

        # Правила, зависящие от confidence
        if confidence is not None and confidence > 0.8:
            return {
                "dialog_state": ANSWER_PROVIDED,
                "action_recommendation": "auto_reply",
                # ...
            }

        # Fallback
        return {
            "dialog_state": current_state,
            "action_recommendation": "auto_reply",
            # ...
        }
```

---

## 4. УЛУЧШЕНИЕ: Параллельное выполнение

### 📋 Текущее состояние

```
language_detection     (5ms)
  ↓
dialog_analysis        (100ms)
  ↓
aggregation            (50ms)
```

Все выполняются последовательно. **Потенциальное время: 155ms**

### 🎯 Решение

```python
# /app/pipeline/graph.py
import asyncio

async def parallel_group_1(state: Dict[str, Any]) -> Dict[str, Any]:
    """Запустить группу узлов параллельно"""
    tasks = [
        language_detection_node(state),
        dialog_analysis_node(state),
    ]

    results = await asyncio.gather(*tasks)

    # Объединить результаты
    merged_state = state.copy()
    for result in results:
        merged_state.update(result)

    return merged_state

# В графе:
workflow.add_node("parallel_group_1", parallel_group_1)
workflow.add_edge("check_cache", "parallel_group_1")
workflow.add_edge("parallel_group_1", "aggregation")
```

**Потенциальное ускорение: 155ms → 100ms (35% быстрее)**

---

## 5. УЛУЧШЕНИЕ: Условное выполнение multihop

### 📋 Текущее состояние

```
reranking
  ↓
multihop (всегда выполняется)
```

### 🎯 Решение

Skipped if high confidence уже реализовано, но его можно улучшить:

```python
# /app/nodes/multihop/node.py (улучшение)
class MultihopNode(BaseNode):
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        params = _get_params()
        skip_if_high_confidence = params.get("skip_if_high_confidence", True)
        high_confidence_threshold = params.get("high_confidence_threshold", 0.8)

        confidence = state.get("confidence", 0.0)

        # УЛУЧШЕНИЕ: Добавить логирование
        if skip_if_high_confidence and confidence >= high_confidence_threshold:
            print(f"✅ multihop: Пропущен (confidence {confidence:.2f} >= threshold {high_confidence_threshold})")
            return {
                "multihop_used": False,
                "hops_performed": 0,
                "docs": state.get("docs", []),
                "confidence": confidence
            }

        # ... rest of code
```

---

## 6. ДОКУМЕНТАЦИЯ: Добавить контракты в docstrings

### 📋 Текущее состояние

Узлы не документируют контракты входа/выхода.

### 🎯 Решение

```python
# /app/nodes/reranking/node.py (пример)
class RerankingNode(BaseNode):
    """
    Переранжирование документов по релевантности.

    INPUT CONTRACTS:
    ================
    Обязательные:
        - question: str - пользовательский запрос
        - docs: List[str] - документы из поиска (не пустой список)

    Опциональные:
        - rerank_model: str - модель переранжирования (default: cross-encoder)

    OUTPUT CONTRACTS:
    =================
    Всегда возвращает:
        - docs: List[str] - переранжированные документы
        - rerank_scores: List[float] - скоры переранжирования
        - confidence: float - скор лучшего документа

    FAILURE MODES:
    ==============
    1. docs пуста → возвращает пустой результат
    2. rerank_model недоступна → fallback к исходному порядку

    DEPENDENCIES:
    ==============
    - Должен работать после узла поиска (retrieve, hybrid_search, fusion)
    - Должен быть ДО multihop (multihop использует rerank_scores)

    EXAMPLES:
    =========
    >>> state = {"question": "...", "docs": [...]}
    >>> node = RerankingNode()
    >>> result = await node.execute(state)
    >>> assert len(result["docs"]) == len(result["rerank_scores"])
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        question = state.get("question", "")
        docs = state.get("docs", [])

        if not docs:
            print(f"⚠️ {self.name}: docs пуста, возвращаю пустой результат")
            return {"docs": [], "rerank_scores": []}

        # ... rest of code
```

---

## 7. ТЕСТИРОВАНИЕ: Добавить тесты контрактов

### 📋 Описание

Создать набор тестов для проверки контрактов каждого узла:

```python
# /tests/test_node_contracts.py
import pytest
from app.pipeline.state import State

@pytest.mark.asyncio
async def test_reranking_node_empty_docs():
    """Reranking должен обрабатывать пустой список docs"""
    node = RerankingNode()
    state = {
        "question": "test",
        "docs": []
    }

    result = await node.execute(state)

    assert result["docs"] == []
    assert result["rerank_scores"] == []

@pytest.mark.asyncio
async def test_fusion_requires_both_results():
    """Fusion требует vector_results И lexical_results"""
    node = FusionNode()

    # Только vector
    state_vector_only = {
        "vector_results": [{"content": "doc1"}],
        "lexical_results": []
    }

    # Должна быть ошибка или graceful degradation
    result = await node.execute(state_vector_only)

    # В зависимости от реализации:
    # assert result["docs"] == [...]  # graceful degradation
    # or pytest.raises(ValueError)     # strict validation

@pytest.mark.asyncio
async def test_multihop_skipped_high_confidence():
    """Multihop должен быть пропущен при высокой уверенности"""
    node = MultihopNode()
    state = {
        "question": "simple question",
        "docs": ["doc1", "doc2"],
        "confidence": 0.95,  # Высокая уверенность
        "rerank_scores": [0.95, 0.85]
    }

    result = await node.execute(state)

    assert result["multihop_used"] == False
    assert result["hops_performed"] == 0
```

---

## 8. КОНФИГУРАЦИЯ: Добавить валидацию pipeline_order.yaml

### 📋 Описание

Добавить проверку при загрузке pipeline_order.yaml:

```python
# /app/services/config_loader/validator.py
def validate_pipeline_order(pipeline_order: List[str]) -> None:
    """
    Валидировать порядок узлов в pipeline_order.yaml

    Проверяет:
    1. Обязательный порядок узлов
    2. Конфликты (например, fusion без retrieve/lexical_search)
    3. Отсутствующие узлы
    """

    # Проверка 1: Безопасность должна быть на месте
    try:
        ig_idx = pipeline_order.index("input_guardrails")
        cc_idx = pipeline_order.index("check_cache")
        assert ig_idx < cc_idx, \
            "input_guardrails должен быть ДО check_cache"
    except ValueError:
        pass  # Node optional

    # Проверка 2: Fusion требует обе функции поиска
    if "fusion" in pipeline_order:
        ret = "retrieve" in pipeline_order
        lex = "lexical_search" in pipeline_order
        if not (ret and lex):
            raise ValueError(
                f"Если используется fusion, ОБА узла должны быть включены: "
                f"retrieve={ret}, lexical_search={lex}"
            )

    # Проверка 3: state_machine должен быть до routing
    try:
        sm_idx = pipeline_order.index("state_machine")
        rt_idx = pipeline_order.index("routing")
        assert sm_idx < rt_idx, \
            "state_machine должен быть ДО routing"
    except ValueError:
        pass

# Использование:
# /app/pipeline/graph.py
pipeline_order = load_pipeline_order()
validate_pipeline_order(pipeline_order)
```

---

## 9. МОНИТОРИНГ: Добавить метрики зависимостей

### 📋 Описание

Отслеживать нарушения контрактов в Langfuse:

```python
# /app/observability/dependency_tracker.py
from app.observability.tracing import observe

class DependencyTracker:
    @staticmethod
    async def track_input_contract(
        node_name: str,
        state: Dict[str, Any],
        required_fields: List[str]
    ):
        """Отследить нарушения входного контракта"""
        missing = [f for f in required_fields if f not in state or state[f] is None]

        if missing:
            print(f"⚠️ {node_name}: Отсутствуют входные поля: {missing}")
            # Отправить метрику в Langfuse
            from langfuse import observe
            observe(
                name=f"{node_name}_contract_violation",
                input={"missing_fields": missing},
                metadata={"severity": "warning"}
            )

# Использование в узле:
class RerankingNode(BaseNode):
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        await DependencyTracker.track_input_contract(
            "reranking",
            state,
            required_fields=["question", "docs"]
        )

        # ... rest of code
```

---

## Чек-лист улучшений

### Приоритет 🔴 (КРИТИЧЕСКИ)
- [ ] Решить проблему с `fusion` и поисками (Вариант 1 + документация)
- [ ] Добавить валидацию `pipeline_order.yaml` в `graph.py`
- [ ] Документировать контракты в docstrings узлов

### Приоритет 🟡 (ВЫСОКИЙ)
- [ ] Улучшить логирование переписей `docs`
- [ ] Добавить юнит-тесты для контрактов
- [ ] Сделать `confidence` в `state_machine` полностью опциональным

### Приоритет 🟢 (СРЕДНИЙ)
- [ ] Реализовать параллельное выполнение группы 1
- [ ] Добавить трекинг нарушений контрактов в Langfuse
- [ ] Улучшить логирование skip conditions

---

## Резюме

**Текущее состояние:** Хорошая архитектура со слабой связанностью, но с несколькими критическими точками упорядочения.

**После улучшений:** Архитектура будет еще более гибкой и надежной с явными контрактами и валидацией.

**Вывод:** Следовать рекомендациям приоритета 🔴 для немедленного повышения надежности.

