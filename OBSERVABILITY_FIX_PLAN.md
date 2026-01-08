# План исправления Observability в Support RAG

## 1. Обзор проблем и решений

### Проблема 1: State Pollution (избыточные входы)
**Текущее состояние:** Каждый узел получает полный state (18KB-30KB)
**Решение:** Реализовать явное определение требуемых входов для каждого узла и фильтрацию в BaseNode
**Статус:** Требует изменения архитектуры BaseNode и каждого узла

### Проблема 2: State Bloat (избыточные выходы)
**Текущее состояние:** Узлы возвращают весь state (53+ поля) вместо только своих изменений
**Решение:** Явное определение выходов и валидация на выходе из узла
**Статус:** Требует изменения возвращаемых значений в каждом узле

### Проблема 3: Пустые выходы спанов
**Текущее состояние:** Спаны функций поиска/embedding не логируют свои результаты
**Решение:** Добавить вывод результатов в спаны функций через контекст Langfuse
**Статус:** Требует изменения функций со @observe декоратором

### Проблема 4: Спаны функций без контрактов
**Текущее состояние:** Функции со @observe не документируют свои inputs/outputs контракты
**Решение:** Добавить docstring контракты для всех функций со @observe
**Статус:** Требует документирования

### Проблема 5: <unknown> узел без имени
**Текущее состояние:** Некоторые узлы не имеют имени в логах
**Решение:** Убедиться что все узлы правильно инициализируют self.name в BaseNode
**Статус:** Требует проверки конфигурации узлов

### Проблема 6: Логирование args/kwargs вместо real data
**Текущее состояние:** Спаны логируют args/kwargs вместо реальных входных данных
**Решение:** Использовать langfuse_context для явного логирования входов/выходов
**Статус:** Требует изменения pattern'а логирования в @observe функциях

---

## 2. Архитектура State Validator

### 2.1 Концепция

Создать систему валидации состояния, которая:
- Определяет входные контракты для каждого узла
- Фильтрует входные данные перед передачей в узел
- Валидирует выходные данные после выполнения узла
- Логирует контрактные нарушения

### 2.2 Компоненты системы

#### StateValidator (Абстрактный базовый класс)
- Метод `get_required_inputs() -> List[str]`: список обязательных входных полей
- Метод `get_optional_inputs() -> List[str]`: список опциональных входных полей
- Метод `get_output_fields() -> List[str]`: список полей, которые узел может возвращать
- Метод `validate_input(state: State) -> bool`: проверка наличия требуемых входов
- Метод `validate_output(output: Dict) -> bool`: проверка что выход содержит только объявленные поля
- Метод `filter_input(state: State) -> State`: возвращает только нужные поля из state

#### InputStateFilter
- Применяется в BaseNode.__call__ перед вызовом execute
- Принимает полный state
- Возвращает отфильтрованный state только с требуемыми полями
- Логирует удаленные поля для отладки (опционально в DEBUG режиме)

#### OutputStateValidator
- Применяется в BaseNode.__call__ после execute
- Проверяет что выход содержит только объявленные поля
- Удаляет лишние поля если они случайно добавлены
- Логирует нарушения контрактов

### 2.3 Структура контрактов

Каждый узел должен определить контракт как часть класса:

```
class MyNode(BaseNode):
    # Контракт определяется в классе
    INPUT_CONTRACT = {
        "required": ["question", "user_id"],
        "optional": ["session_id"]
    }

    OUTPUT_CONTRACT = {
        "fields": ["answer", "confidence", "docs"]
    }
```

Альтернатива через метод:
```
def get_input_contract(self) -> Dict:
    return {
        "required": [...],
        "optional": [...]
    }

def get_output_contract(self) -> Dict:
    return {
        "fields": [...]
    }
```

---

## 3. Описание входов/выходов для каждого узла

### Tier 1: Entry/Exit узлы (telegram_rag_query, rag_query)

#### telegram_rag_query (CHAIN)
**Назначение:** Главный RAG pipeline orchestrator
**Входы (требуемые):**
- `question: str` - пользовательский вопрос
- `user_id: str` - идентификатор пользователя
- `session_id: str` - идентификатор сессии

**Входы (опциональные):**
- `conversation_context: List[Dict]` - контекст беседы (передается как дополнение, не весь state)

**Выходы:**
- `answer: str` - финальный ответ
- `action: str` - рекомендуемое действие (auto_reply, handoff, escalate)
- `confidence: float` - общая уверенность в ответе
- `sources: List[Dict]` - источники ответа с метаданными

**НЕ должны быть в выходе:**
- `conversation_history` - только исходящее, не возвращать весь список
- `docs` - только необходимые для источников
- Внутренние служебные поля (_session_history_loader, etc)

---

### Tier 2: Session & Security узлы

#### session_starter (CHAIN)
**Входы (требуемые):**
- `user_id: str`
- `session_id: str`

**Входы (опциональные):**
- `load_profile: bool` - загружать ли профиль пользователя (из конфига)
- `max_history: int` - количество сообщений истории (из конфига)

**Выходы:**
- `conversation_history: List[Dict]` - сообщения текущей сессии
- `user_profile: Dict` - профиль пользователя (если enabled)
- `_session_history_loader: Callable` - lazy loader для истории других сессий (внутреннее поле)
- `_session_metadata: Dict` - метаданные сессии (внутреннее поле)
- `attempt_count: int` - счетчик попыток обработки

**НЕ должны быть в выходе:**
- Все остальные поля state

---

#### input_guardrails (CHAIN)
**Входы (требуемые):**
- `question: str` - текст вопроса для анализа
- `conversation_history: List[Dict]` - контекст беседы для анализа тона

**Входы (опциональные):**
- `detected_language: str` - язык для контекста

**Выходы:**
- `guardrails_passed: bool` - прошел ли фильтры безопасности
- `guardrails_risk_score: float` - численная оценка риска (0.0-1.0)
- `guardrails_triggered: List[str]` - какие правила сработали (если есть)

**Условные выходы (только если guardrails_passed=false):**
- `guardrails_warning: str` - описание проблемы
- `answer: str` - автоматический ответ (для блокировки)

---

#### output_guardrails (CHAIN)
**Входы (требуемые):**
- `answer: str` - сгенерированный ответ
- `question: str` - исходный вопрос (контекст)

**Входы (опциональные):**
- `docs: List[str]` - источники для валидации

**Выходы:**
- `output_guardrails_passed: bool` - прошла ли санитизация
- `answer: str` - обработанный ответ (может быть отредактирован)
- `output_sanitized: bool` - был ли ответ изменен

---

### Tier 3: Query Processing узлы

#### language_detection (CHAIN)
**Входы (требуемые):**
- `question: str`

**Входы (опциональные):**
- `conversation_history: List[Dict]` - для лучшего определения языка

**Выходы:**
- `detected_language: str` - код языка (en, ru, etc)
- `language_confidence: float` - уверенность определения

---

#### query_translation (CHAIN)
**Входы (требуемые):**
- `question: str`
- `detected_language: str`

**Входы (опциональные):**
- `target_language: str` - в какой язык переводить (по умолчанию en)

**Выходы:**
- `translated_query: str` - переведенный вопрос

---

#### easy_classification (CHAIN)
**Входы (требуемые):**
- `question: str` - вопрос для классификации

**Входы (опциональные):**
- `detected_language: str` - язык вопроса

**Выходы:**
- `matched_intent: str` - определённый интент
- `matched_category: str` - определённая категория
- `semantic_intent: str` - семантический интент
- `semantic_intent_confidence: float` - уверенность семантического интента
- `semantic_category: str` - семантическая категория

---

#### dialog_analysis (CHAIN)
**Входы (требуемые):**
- `question: str` - текущий вопрос
- `conversation_history: List[Dict]` - историческая беседа

**Входы (опциональные):**
- `dialog_state: str` - текущее состояние диалога

**Выходы:**
- `dialog_analysis: Dict` - результаты анализа диалога
  - `sentiment: Dict` - анализ тональности
  - `entity_mentions: List[str]` - упомянутые сущности
  - `dialog_intent: str` - интент текущего диалога
  - `conversation_flow: str` - оценка потока беседы
- `sentiment: Dict` - только тональность текущего сообщения

---

### Tier 4: Retrieval & Search узлы

#### check_cache (CHAIN)
**Входы (требуемые):**
- `question: str`

**Входы (опциональные):**
- `top_k: int` - количество результатов из кэша (по умолчанию 1)

**Выходы:**
- `cache_hit: bool` - найдено ли в кэше
- `cache_key: str` - используемый ключ кэша

**Условные выходы (если cache_hit=true):**
- `answer: str` - закэшированный ответ
- `confidence: float` - уверенность (1.0 для точного совпадения)
- `docs: List[str]` - закэшированные источники
- `cache_reason: str` - причина hit (exact_match, semantic_match)
- `question_embedding: List[float]` - embedding вопроса

**НЕ должны быть в выходе:**
- conversation_history (не модифицируется этим узлом)
- все остальные поля state

---

#### metadata_filtering (CHAIN)
**Входы (требуемые):**
- `question: str` - для определения фильтров

**Входы (опциональные):**
- `user_id: str` - для персональной фильтрации
- `matched_category: str` - подсказка для фильтрации

**Выходы:**
- `filter_used: bool` - применился ли фильтр
- `filtering_reason: str` - причина применения/отказа
- `applied_filters: Dict` - какие фильтры применены
- `filter_confidence: float` - уверенность в выборе фильтров

---

#### hybrid_search (CHAIN)
**Входы (требуемые):**
- `aggregated_query: str` ИЛИ `question: str` - поисковый запрос
- `applied_filters: Dict` - метаданные фильтры (если есть)

**Входы (опциональные):**
- `top_k: int` - количество результатов (по умолчанию 5)

**Выходы:**
- `docs: List[str]` - найденные документы
- `scores: List[float]` - scores релевантности
- `hybrid_used: bool` - был ли использован гибридный поиск
- `search_time_ms: float` - время поиска

---

#### metadata_filtering (CHAIN) - для search контекста
**Входы (требуемые):**
- `docs: List[str]` - результаты поиска для фильтрации

**Выходы:**
- `docs: List[str]` - отфильтрованные документы (может быть пусто)
- `filter_applied: bool`
- `original_count: int` - исходное количество
- `final_count: int` - после фильтрации

---

#### reranking (CHAIN)
**Входы (требуемые):**
- `docs: List[str]` - документы для переранжирования
- `question: str` - контекст для переранжирования
- `scores: List[float]` - исходные scores

**Входы (опциональные):**
- `top_k: int` - количество top результатов

**Выходы:**
- `docs: List[str]` - переранжированные документы
- `rerank_scores: List[float]` - новые scores
- `confidence: float` - уверенность в переранжировании

---

#### aggregation (CHAIN)
**Входы (требуемые):**
- `docs: List[str]` - документы для агрегации
- `scores: List[float]` - scores документов

**Входы (опциональные):**
- `aggregation_method: str` - способ агрегации (max, mean, etc)

**Выходы:**
- `aggregated_query: str` - агрегированный запрос
- `merged_context: str` - объединённый контекст документов

---

#### multihop (CHAIN) - если используется
**Входы (требуемые):**
- `question: str` - исходный вопрос
- `docs: List[str]` - начальные документы

**Входы (опциональные):**
- `max_hops: int` - максимальное количество hops
- `use_multihop: bool` - включить ли multihop

**Выходы:**
- `multihop_used: bool` - был ли multihop использован
- `hops_performed: int` - количество сделанных hops
- `docs: List[str]` - финальные документы после всех hops

---

### Tier 5: Analysis & Generation узлы

#### state_machine (CHAIN)
**Входы (требуемые):**
- `dialog_analysis: Dict` - анализ диалога

**Входы (опциональные):**
- `dialog_state: str` - текущее состояние (по умолчанию INITIAL)
- `attempt_count: int` - попытки обработки

**Выходы:**
- `dialog_state: str` - новое состояние диалога
- `attempt_count: int` - обновленный счетчик
- `action_recommendation: str` - рекомендуемое действие
- `escalation_reason: str` - причина эскалации (если есть)
- `state_behavior: str` - описание поведения в новом состоянии

---

#### generation (CHAIN)
**Входы (требуемые):**
- `question: str`
- `docs: List[str]` ИЛИ `merged_context: str` - источники для ответа

**Входы (опциональные):**
- `system_prompt: str` - переопределение system prompt
- `human_prompt: str` - переопределение human prompt
- `aggregated_query: str` - преобразованный запрос

**Выходы:**
- `answer: str` - сгенерированный ответ
- `generation_time_ms: float` - время генерации

**Условные выходы (если escalation):**
- `escalation_message: str` - сообщение эскалации

---

#### routing (CHAIN)
**Входы (требуемые):**
- `question: str` - для контекста
- `answer: str` - сгенерированный ответ

**Входы (опциональные):**
- `confidence: float` - уверенность в ответе
- `best_doc_metadata: Dict` - метаданные лучшего документа
- `detected_language: str` - язык ответа

**Выходы:**
- `action: str` - финальное действие (auto_reply, handoff, escalate, regenerate)
- `routing_reason: str` - причина выбора действия
- `escalation_triggered: bool` - была ли триггирована эскалация

**Условные выходы:**
- `escalation_message: str` - сообщение для пользователя при эскалации
- `escalation_decision: Dict` - детали решения об эскалации

---

### Tier 6: Post-Processing узлы

#### archive_session (CHAIN)
**Входы (требуемые):**
- `question: str` - для архива
- `answer: str` - для архива
- `session_id: str` - какую сессию архивировать

**Входы (опциональные):**
- `archive: bool` - включить ли архивирование

**Выходы:**
- `archived: bool` - успешно ли заархивировано

---

#### store_in_cache (CHAIN)
**Входы (требуемые):**
- `question: str` - что кэшировать
- `answer: str` - кэшируемый ответ
- `cache_key: str` - ключ кэша

**Входы (опциональные):**
- `docs: List[str]` - источники для кэша
- `confidence: float` - уверенность ответа
- `ttl_seconds: int` - время жизни кэша

**Выходы:**
- `cached: bool` - успешно ли закэшировано

**НЕ должны быть в выходе:**
- Весь state целиком (основная ошибка!)
- conversation_history, docs, и др. служебные поля

---

## 4. Изменения в структуре узлов

### 4.1 Изменения в BaseNode

**Что изменить:**
1. Добавить методы для определения контрактов узла
   - `get_input_contract()` - возвращает требуемые и опциональные входы
   - `get_output_contract()` - возвращает поля выхода

2. Добавить фильтрацию входов перед execute
   - В `__call__` применить InputStateFilter перед передачей state в execute
   - Логировать какие поля удалены (опционально в DEBUG)

3. Добавить валидацию выходов после execute
   - В `__call__` применить OutputStateValidator после execute
   - Удалить лишние поля если они случайно добавлены
   - Логировать нарушения контрактов

4. Улучшить логирование в Langfuse
   - Логировать только отфильтрованные входы
   - Логировать только объявленные выходы
   - Использовать langfuse_context.update_current_observation для добавления метаданных

### 4.2 Изменения в каждом узле (Tier 1-6)

**ДЛЯ КАЖДОГО УЗЛА:**

1. Определить INPUT_CONTRACT или реализовать get_input_contract()
   - Перечислить обязательные поля
   - Перечислить опциональные поля
   - Указать типы данных

2. Определить OUTPUT_CONTRACT или реализовать get_output_contract()
   - Перечислить выходные поля
   - Указать типы данных
   - Отметить условные выходы

3. Изменить return statement в execute()
   - Возвращать ТОЛЬКО новые/измененные поля
   - НЕ возвращать весь state
   - Примеры:
     - session_starter: возвращать только `{conversation_history, user_profile, ...}` (5 полей)
     - check_cache: возвращать только `{cache_hit, cache_key, ...}` (зависит от hit/miss)
     - store_in_cache: возвращать только `{cached: bool}` (НЕ весь state)

### 4.3 Изменения в функциях со @observe

**ДЛЯ КАЖДОЙ ФУНКЦИИ СО @observe:**

1. Добавить docstring контракт
   - Описать Required Inputs
   - Описать Optional Inputs
   - Описать Guaranteed Outputs
   - Описать Conditional Outputs

2. Явно логировать входы через langfuse_context
   - Вместо полагания на args/kwargs
   - Передавать реальные данные функции

3. Явно логировать выходы через langfuse_context
   - Не оставлять пусто
   - Передавать результаты функции

4. Присвоить имя узлу через langfuse_context
   - Если это вложенный узел

**Функции для исправления:**
- vector_search() - логировать результаты поиска
- lexical_search_db() - логировать результаты
- search_hybrid() - логировать объединенные результаты
- get_embedding() - логировать embedding размер и первые значения
- llm_dialog_analysis_node() - логировать результаты анализа
- llm_aggregation_node() - логировать агрегированный результат
- all query expansion/translation functions - логировать выходы

---

## 5. Создание StateValidator системы

### 5.1 Новые файлы

**Создать: app/observability/state_validator.py**
- Абстрактный класс StateValidator
- Методы для валидации и фильтрации

**Создать: app/observability/input_state_filter.py**
- Класс InputStateFilter
- Применение фильтрации входов

**Создать: app/observability/output_state_validator.py**
- Класс OutputStateValidator
- Валидация и очистка выходов

### 5.2 Интеграция с BaseNode

BaseNode.__call__ должен использовать:
1. InputStateFilter для фильтрации входов перед execute
2. OutputStateValidator для валидации выходов после execute

### 5.3 Интеграция с графом

При создании графа в graph.py:
- Убедиться что все узлы имеют proper имена
- Логировать контрактные нарушения на уровне графа (опционально)

---

## 6. Решение проблемы <unknown> узла

### 6.1 Причины

1. Некоторые узлы создаются с некорректным именем
2. Возможно это узел из conditioning logic или edge function

### 6.2 Решение

1. Проверить все узлы в graph.py на наличие имен
2. Убедиться что BaseNode.__init__ всегда устанавливает self.name
3. Проверить что langfuse_context.update_current_observation вызывается с правильным именем

---

## 7. Решение проблемы args/kwargs логирования

### 7.1 Текущая проблема

Спаны логируют:
```
"input": "{\"args\": [], \"kwargs\": {...}}"
```

Это происходит потому что @observe декоратор автоматически захватывает аргументы функции.

### 7.2 Решение

Для каждой функции со @observe:
1. Отключить автоматическое логирование args/kwargs
2. Явно передавать входные данные через langfuse_context.update_current_observation()
3. Явно передавать выходные данные через langfuse_context

Примерный паттерн:
```
@observe(as_type="span")
async def my_function(param1, param2):
    # Явно логируем входы
    langfuse_context.update_current_observation(
        input={"param1": param1, "param2": param2}
    )

    # Выполняем логику
    result = ...

    # Явно логируем выходы
    langfuse_context.update_current_observation(
        output=result
    )

    return result
```

---

## 8. Обратная совместимость и миграция

### 8.1 Фазы внедрения

**Фаза 1: Инфраструктура (StateValidator система)**
- Создать новые классы валидации
- Интегрировать в BaseNode
- НЕ менять узлы еще

**Фаза 2: Критические узлы**
- Обновить TOP узлы (session_starter, input_guardrails, generation, routing)
- Убедиться что логи улучшились

**Фаза 3: Остальные узлы**
- Обновить оставшиеся узлы поэтапно
- Тестировать после каждого

**Фаза 4: Функции со @observe**
- Обновить функции поиска/embedding
- Обновить функции LLM

### 8.2 Выключение и включение валидации

- Добавить флаг в конфиг: `validation.enabled: bool`
- Добавить флаг: `validation.strict_mode: bool`
  - true = удалять лишние поля, логировать ошибки
  - false = только логировать, не удалять

---

## 9. Метрики успеха

После внедрения следует достичь:

| Метрика | Текущее | Целевое |
|---------|---------|---------|
| Размер input для check_cache | 18.8 KB | <1 KB |
| Размер input для routing | 29.6 KB | <5 KB |
| Количество выходных полей в узле | 53 | 3-8 |
| Узлы со спанами без выходов | 5 | 0 |
| Узлы с <unknown> именем | 1+ | 0 |
| Функции без контрактов | 15+ | 0 |
| Логирование args/kwargs вместо data | 10+ функций | 0 |

---

## 10. Чек-лист реализации

### По компонентам:

- [ ] Создать StateValidator абстрактный класс
- [ ] Создать InputStateFilter
- [ ] Создать OutputStateValidator
- [ ] Обновить BaseNode для использования фильтров
- [ ] Добавить контракты для session_starter
- [ ] Добавить контракты для input_guardrails
- [ ] Добавить контракты для check_cache
- [ ] Добавить контракты для generation
- [ ] Добавить контракты для routing
- [ ] Добавить контракты для всех остальных узлов (21 узел)
- [ ] Обновить vector_search() функцию
- [ ] Обновить lexical_search_db() функцию
- [ ] Обновить все остальные @observe функции (15+)
- [ ] Найти и исправить <unknown> узел
- [ ] Добавить тесты для валидации
- [ ] Обновить документацию узлов
- [ ] Провести E2E тестирование
- [ ] Собрать новые логи и сравнить размеры

---

## 11. Структура документации в docstring узла

Каждый узел должен иметь docstring в execute() метода:

```
"""
[Описание узла]

Contracts:
    Input:
        Required:
            - field_name (type): Описание
        Optional:
            - field_name (type): Описание

    Output:
        Guaranteed:
            - field_name (type): Описание
        Conditional (when condition):
            - field_name (type): Описание

    State Impact:
        - Какие поля изменяются
        - Какие поля удаляются
        - Новые поля добавляются
"""
```

---

## 12. Финальные замечания

### Почему это важно:

1. **Читаемость логов:** 1KB вместо 30KB = легче анализировать
2. **Отладка:** Ясные входы/выходы = легче найти проблему
3. **Производительность:** Меньше данных в Langfuse = дешевле и быстрее
4. **Надежность:** Явные контракты = меньше ошибок
5. **Документирование:** Код становится самодокументирующимся

### Риски:

1. Обратная совместимость - решение через strict_mode флаг
2. Изменение поведения узлов - решение через поэтапное внедрение
3. Производительность валидации - решение через опциональное отключение в PROD

