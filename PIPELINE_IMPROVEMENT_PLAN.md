# 🚀 План улучшения RAG Pipeline

> **Версия:** 1.0  
> **Дата создания:** 2026-01-04  
> **Статус:** В разработке

---

## 📋 Содержание

1. [Обзор проблем](#обзор-проблем)
2. [Архитектура конфигурации](#архитектура-конфигурации)
3. [Фазы реализации](#фазы-реализации)
4. [Детальные задачи](#детальные-задачи)
5. [Технические нюансы](#технические-нюансы)
6. [Критерии готовности](#критерии-готовности)

---

## 🔍 Обзор проблем

### Критические (🔴)
| # | Проблема | Влияние |
|---|----------|---------|
| 1 | Грязная история диалога | LLM получает шум, ухудшается качество |
| 2 | Aggregation не использует контекст | Потеря связи между сообщениями |
| 4 | Нет документов для техпроблем + хардкод категорий | Нерелевантные ответы |
| 5 | Multihop обрезает до 1 документа | Потеря информации |
| 6 | Неверный порядок multihop/rerank | Неэффективный reranking |
| 9 | Routing игнорирует низкий confidence | Ответы с 0.001% уверенности |
| 10 | Prompt Routing с пустой историей | Несовместимость структур данных |

### Средние (🟡)
| # | Проблема | Влияние |
|---|----------|---------|
| 3 | Низкая уверенность классификации | Неверные интенты |
| 11 | State Machine всегда INITIAL | Нет адаптации под контекст |
| 13 | Несоответствие языка ответа | UX проблема |

### Низкие (🟢)
| # | Проблема | Влияние |
|---|----------|---------|
| 12 | Дублирование полей в State | Технический долг |

---

## 🏗️ Архитектура конфигурации

### Почему YAML?
- ✅ Поддержка комментариев (критично для документирования)
- ✅ Читаемый синтаксис для вложенных структур
- ✅ Многострочные строки для промптов
- ✅ Якоря и ссылки для переиспользования значений

### Зависимости
```
# requirements.txt
PyYAML>=6.0.1
```

### Структура файлов

```
app/
├── nodes/
│   ├── {node_name}/
│   │   ├── __init__.py
│   │   ├── node.py
│   │   ├── config.yaml          # ← Конфигурация ноды
│   │   └── ...
│   │
│   └── _shared_config/          # ← Общие конфиги
│       ├── intents_registry.yaml
│       ├── system_phrases.yaml
│       └── languages.yaml
│
├── pipeline/
│   ├── __init__.py
│   ├── graph.py                # Читает pipeline_config.yaml
│   ├── state.py
│   ├── config.py               # Загрузчик YAML конфига
│   ├── pipeline_config.yaml    # ← Основной конфиг (миграция с JSON)
│   └── pipeline_config.json    # ⚠️ DEPRECATED - удалить после миграции
│
└── services/
    └── config_loader/
        ├── __init__.py
        ├── loader.py           # Единый загрузчик конфигов
        └── validator.py        # Валидация схемы

scripts/
├── build_config.py             # Сборка всех конфигов в один
└── refresh_intents.py          # Обновление реестра интентов из БД
```

### Схема config.yaml для ноды

```yaml
# Пример: app/nodes/reranking/config.yaml

# Метаданные ноды (обязательные)
node:
  name: "rerank"                    # Должно совпадать с именем в pipeline
  version: "1.0.0"
  enabled: true                     # Можно переопределить в pipeline_config

# Параметры (специфичны для каждой ноды)
parameters:
  confidence_threshold: 0.3
  top_k: 5
  model_name: "BAAI/bge-reranker-v2-m3"
  batch_size: 32

# Опциональные секции
timeouts:
  inference_ms: 5000
  
metrics:
  track_latency: true
  track_confidence: true

# Документация (для генерации UI/справки)
meta:
  description: "Переранжирование документов cross-encoder моделью"
  author: "team"
  parameters_help:
    confidence_threshold: "Минимальный score для принятия документа"
    top_k: "Количество документов для возврата"
```

### Схема pipeline_config.yaml

```yaml
# app/pipeline/pipeline_config.yaml

version: "2.0"
updated_at: "2026-01-04"

# Глобальные настройки
global:
  default_language: "ru"
  confidence_threshold: 0.3      # Глобальный порог (можно переопределить в ноде)
  debug_mode: false

# Кэширование
cache:
  enabled: true
  backend: "redis"               # redis | memory
  redis_url: "${REDIS_URL}"      # Поддержка env variables
  ttl_seconds: 86400
  max_entries: 1000

# Порядок выполнения нод (ВАЖНО: порядок определяет flow!)
pipeline:
  - name: session_starter
    enabled: true
    
  - name: check_cache
    enabled: true
    # Условный переход при cache hit
    on_hit: store_in_cache
    on_miss: continue
    
  - name: dialog_analysis
    enabled: true
    
  - name: state_machine
    enabled: true
    
  - name: aggregate
    enabled: true
    
  - name: fasttext_classify
    enabled: true
    
  - name: metadata_filter
    enabled: true
    
  - name: hybrid_search
    enabled: true
    
  # ⚠️ ВАЖНО: rerank ПЕРЕД multihop!
  - name: rerank
    enabled: true
    
  - name: multihop
    enabled: true
    
  - name: route
    enabled: true
    # Условный переход
    on_auto_reply: prompt_routing
    on_handoff: archive_session
    
  - name: prompt_routing
    enabled: true
    
  - name: generate
    enabled: true
    
  - name: archive_session
    enabled: true
    
  - name: store_in_cache
    enabled: true

# Переопределение параметров нод (опционально)
node_overrides:
  rerank:
    parameters:
      top_k: 3
  multihop:
    parameters:
      output_docs_count: 5
```

---

## 📅 Фазы реализации

### Фаза 0: Подготовка (1 день) ✅ ВЫПОЛНЕНО
- [x] Добавить `PyYAML>=6.0.1` в requirements.txt
- [x] Создать `app/services/config_loader/` с базовым загрузчиком
- [x] Создать `app/nodes/_shared_config/` директорию

### Фаза 1: Миграция на YAML (2-3 дня) ✅ ВЫПОЛНЕНО
- [x] Конвертировать `pipeline_config.json` → `pipeline_config.yaml`
- [x] Обновить `app/pipeline/graph.py` для чтения YAML
- [x] Создать `config.yaml` для каждой ноды (шаблоны)
- [ ] Тестировать что pipeline работает как раньше

### Фаза 2: Критические исправления (3-4 дня) ✅ ВЫПОЛНЕНО
- [x] Системные фразы + фильтрация истории
- [x] Изменить порядок: rerank → multihop (в pipeline_config.yaml)
- [x] Multihop отдаёт N документов (output_docs_count: 3)
- [x] Prompt Routing с правильной историей (conversation_history)

### Фаза 3: Intent Registry (2 дня)
- [ ] Сервис извлечения интентов из БД
- [ ] Автогенерация `intents_registry.yaml`
- [ ] Классификатор использует динамические категории

### Фаза 4: State Machine Rules (2 дня)
- [ ] Декларативные правила в `rules.yaml`
- [ ] Rule Engine для обработки правил
- [ ] Интеграция с prompt_routing

### Фаза 5: Улучшения (2-3 дня)
- [ ] LLM Aggregation + Lightweight с историей
- [ ] Детекция языка в ответах
- [ ] Скрипт `build_config.py`


---

## 📝 Детальные задачи

### Задача 1: Грязная история диалога

**Файл:** `app/nodes/_shared_config/system_phrases.yaml`

```yaml
version: "1.0"

# Паттерны для фильтрации (НЕ сохранять в историю)
filter_patterns:
  # Русские системные фразы
  - regex: "Извините, не смог обработать"
    type: "error"
  - regex: "Ошибка подключения к сервису"
    type: "error"  
  - regex: "Попробуйте позже"
    type: "retry"
  - regex: "Соединяю с оператором"
    type: "handoff"
    
  # English system phrases
  - regex: "Sorry, couldn't process"
    type: "error"
  - regex: "Connecting you to"
    type: "handoff"

# Фразы для отображения (бот берёт отсюда)
display_phrases:
  error:
    ru: "Извините, произошла ошибка. Попробуйте ещё раз."
    en: "Sorry, an error occurred. Please try again."
  handoff:
    ru: "Соединяю вас с оператором поддержки..."
    en: "Connecting you with a support agent..."
  greeting:
    ru: "Здравствуйте! Чем могу помочь?"
    en: "Hello! How can I help you?"
```

**API эндпоинт:**
```
GET /api/v1/config/system-phrases
Response: { "filter_patterns": [...], "display_phrases": {...} }
```

**Где фильтровать:**
- `archive_session` node — перед сохранением в БД
- Альтернатива: `session_starter` — при загрузке (ленивая очистка)

**Нюансы:**
- Telegram бот запрашивает фразы при старте + кэширует
- При обновлении `system_phrases.yaml` — бот должен перезагрузить
- Добавить endpoint `POST /api/v1/config/reload` для горячей перезагрузки

---

### Задача 2: Aggregation с историей

**Файл:** `app/nodes/aggregation/config.yaml`

```yaml
node:
  name: aggregate
  enabled: true

parameters:
  mode: "lightweight"           # lightweight | llm
  history_messages_count: 3     # Сколько последних сообщений брать
  include_assistant_responses: true
  
llm:
  model: "gpt-4o-mini"
  temperature: 0
  max_tokens: 200
  prompt_template: |
    На основе истории диалога и текущего вопроса, сформулируй полный вопрос.
    
    История:
    {history}
    
    Текущий вопрос: {question}
    
    Полный вопрос:

lightweight:
  # Формат агрегации
  template: "[Контекст: {last_assistant_response}] Вопрос: {current_question}"
  # Если нет истории — просто вопрос
  fallback_template: "{current_question}"
```

**Нюансы:**
- Если `conversation_history` пустая — использовать `session_history[].summary`
- LLM aggregation дороже, но качественнее — оставить как опцию
- Для lightweight: брать последний ответ ассистента + текущий вопрос

---

### Задача 3: Порог классификации

**Файл:** `app/nodes/easy_classification/config.yaml`

```yaml
node:
  name: fasttext_classify
  enabled: true

parameters:
  intent_confidence_threshold: 0.3
  category_confidence_threshold: 0.3
  
  # Что возвращать при низком confidence
  fallback:
    intent: "unknown"
    category: "General"
    
  # Игнорировать результат если ниже порога
  skip_if_low_confidence: true
```

**Логика в ноде:**
```
if intent_confidence < threshold:
    return { semantic_intent: "unknown", ... }
```

---

### Задача 4: Dynamic Intent Registry

**Проблема:** Категории захардкожены, а должны извлекаться из БД.

**Решение:**

**Файл:** `app/services/intent_registry/registry.py`

```python
class IntentRegistry:
    """
    Сервис для динамического управления интентами и категориями.
    Загружает из БД, кэширует, предоставляет API.
    """
    
    async def refresh_from_db(self):
        """
        SQL: SELECT DISTINCT 
               metadata->>'intent' as intent,
               metadata->>'category' as category
             FROM documents
        """
        
    def get_all_categories(self) -> List[str]:
        """Для zero-shot классификатора"""
        
    def get_intents_for_category(self, category: str) -> List[str]:
        """Для фильтрации"""
        
    def to_yaml(self, path: str):
        """Экспорт в YAML для версионирования"""
```

**Автогенерируемый файл:** `app/nodes/_shared_config/intents_registry.yaml`

```yaml
# ⚠️ АВТОГЕНЕРИРУЕМЫЙ ФАЙЛ
# Не редактируйте вручную!
# Скрипт: scripts/refresh_intents.py

_meta:
  generated_at: "2026-01-04T12:00:00Z"
  source: "postgres:documents.metadata"
  documents_count: 10

categories:
  - name: "Shipping"
    intents:
      - id: "track_order"
        examples_count: 1
        requires_handoff: false
      - id: "change_address"
        examples_count: 1
        requires_handoff: false

  - name: "Account Management"
    intents:
      - id: "cancel_subscription"
        examples_count: 1
        requires_handoff: true
```

**Как использовать в классификаторе:**
```python
registry = IntentRegistry()
categories = registry.get_all_categories()
# ["Shipping", "Account Management", "Billing", ...]

# Zero-shot classifier использует этот список
result = classifier.classify(query, candidate_labels=categories)
```

**Скрипт:** `scripts/refresh_intents.py`
- Запускать при деплое
- Запускать после ingestion новых документов
- Cron job раз в день (опционально)

---

### Задача 5-6: Порядок Rerank → Multihop

**Текущий порядок (неоптимальный):**
```
hybrid_search (10 docs) → multihop (1 doc) → rerank (1 doc) ❌
```

**Новый порядок:**
```
hybrid_search (10 docs) → rerank (5 docs) → multihop (3 docs) ✅
```

**Изменения в `pipeline_config.yaml`:**
```yaml
pipeline:
  # ...
  - name: hybrid_search
    enabled: true
  - name: rerank          # ← Раньше был после multihop
    enabled: true
  - name: multihop        # ← Теперь после rerank
    enabled: true
```

**Конфиг multihop:** `app/nodes/multihop/config.yaml`

```yaml
node:
  name: multihop
  enabled: true

parameters:
  # ⚠️ ВАЖНО: Сколько документов передавать дальше
  output_docs_count: 3
  
  max_hops: 2
  complexity_threshold: 1.5
  
  # Оптимизация: пропустить если уже высокий confidence
  skip_if_high_confidence: true
  high_confidence_threshold: 0.8
```

**Изменения в `multihop/node.py`:**
```python
# Было:
return { "docs": [merged_context] }  # 1 документ

# Станет:
output_count = config["output_docs_count"]  # из конфига
return { 
    "docs": [merged_context] + related_docs[:output_count-1]
}
```

---

### Задача 9: Routing + Confidence

**Файл:** `app/nodes/routing/config.yaml`

```yaml
node:
  name: route
  enabled: true

parameters:
  # Минимальный confidence для автоответа
  # ⚠️ Установите 0 для отключения проверки
  min_confidence_auto_reply: 0.0
  
  # Использовать escalation_decision из dialog_analysis
  respect_escalation_decision: true
  
  # Использовать requires_handoff из metadata документа
  respect_requires_handoff: true

# Приоритет решений (от высшего к низшему)
decision_priority:
  1: "safety_violation"        # Всегда handoff
  2: "escalation_requested"    # Пользователь попросил
  3: "requires_handoff"        # Документ требует
  4: "low_confidence"          # Ниже порога
  5: "auto_reply"              # Обычный ответ
```

**Анализ: нужен ли routing node?**

| Функция | dialog_analysis | state_machine | routing |
|---------|----------------|---------------|---------|
| Определить frustration | ✅ | - | - |
| Определить escalation_requested | ✅ | - | - |
| Определить dialog_state | - | ✅ | - |
| Учесть confidence | - | ✅ | ✅ |
| Учесть requires_handoff | - | - | ✅ |
| Финальное решение action | - | - | ✅ |

**Вывод:** Routing node нужен как финальный арбитр, но можно упростить.

---

### Задача 10: Prompt Routing + История

**Проблема:** `session_history` имеет формат `{session_id, outcome, summary}`, а ожидается `{role, content}`.

**Решение:**
1. Использовать `conversation_history` (правильный формат)
2. Если пустой — брать `summary` из `session_history`

**Файл:** `app/nodes/prompt_routing/config.yaml`

```yaml
node:
  name: prompt_routing
  enabled: true

parameters:
  # Источник истории  
  history_source: "conversation_history"  # conversation_history | session_history
  
  # Максимум сообщений в промпте
  max_history_messages: 5
  
  # Включать контекстную информацию
  include_user_profile: true
  include_entities: true
```

**Изменения в коде:**
```python
def _format_history(state):
    # 1. Пробуем conversation_history
    conv_history = state.get("conversation_history", [])
    if conv_history:
        # Фильтруем системные сообщения (из system_phrases)
        return format_conv_history(conv_history[-N:])
    
    # 2. Fallback на session_history
    session_history = state.get("session_history", [])
    if session_history:
        return format_session_summary(session_history[-N:])
    
    return ""
```

---

### Задача 11: State Machine Rules Engine

**Файл:** `app/nodes/state_machine/rules.yaml`

```yaml
version: "1.0"
description: "Декларативные правила для определения состояния диалога"

# Правила проверяются по порядку, первое сработавшее применяется
rules:

  # === ПРИОРИТЕТ 1: Safety ===
  - id: "safety_block"
    description: "Блокировка при нарушении safety"
    priority: 100
    conditions:
      - field: "safety_violation"
        operator: "eq"
        value: true
    actions:
      set_state: "BLOCKED"
      set_action: "block"

  # === ПРИОРИТЕТ 2: Explicit Escalation ===
  - id: "user_requests_human"
    description: "Пользователь явно просит оператора"
    priority: 90
    conditions:
      - field: "dialog_analysis.escalation_requested"
        operator: "eq"
        value: true
    actions:
      set_state: "ESCALATE"
      set_action: "handoff"

  # === ПРИОРИТЕТ 3: Emotional States ===
  - id: "angry_user"
    description: "Пользователь злится"
    priority: 80
    conditions:
      - field: "sentiment.label"
        operator: "eq"
        value: "angry"
      - field: "sentiment.score"
        operator: "gte"
        value: 0.7
    actions:
      set_state: "ESCALATE"
      set_action: "handoff"
      
  - id: "frustrated_user"
    description: "Пользователь фрустрирован"
    priority: 75
    conditions:
      - field: "sentiment.label"
        operator: "in"
        value: ["frustrated", "negative"]
      - field: "sentiment.score"
        operator: "gte"
        value: 0.6
    actions:
      set_state: "EMPATHY_MODE"
      increment_attempts: true

  # === ПРИОРИТЕТ 4: Confidence ===
  - id: "very_low_confidence"
    description: "Система совсем не уверена"
    priority: 70
    conditions:
      - field: "confidence"
        operator: "lt"
        value: 0.1
    actions:
      set_state: "LOW_CONFIDENCE"
      increment_attempts: true
      
  - id: "low_confidence"
    description: "Низкая уверенность"
    priority: 65
    conditions:
      - field: "confidence"
        operator: "lt"
        value: 0.3
    actions:
      set_state: "CLARIFY"
      increment_attempts: true

  # === ПРИОРИТЕТ 5: Loop Detection ===
  - id: "stuck_in_loop"
    description: "Пользователь застрял"
    priority: 60
    conditions:
      - field: "attempt_count"
        operator: "gte"
        value: 3
    actions:
      set_state: "STUCK_LOOP"
      set_action: "suggest_handoff"

  - id: "repeated_question"
    description: "Повторный вопрос"
    priority: 55
    conditions:
      - field: "dialog_analysis.repeated_question"
        operator: "eq"
        value: true
      - field: "attempt_count"
        operator: "gte"
        value: 2
    actions:
      set_state: "REPEATED_ISSUE"
      increment_attempts: true

  # === ПРИОРИТЕТ 6: Positive ===
  - id: "gratitude"
    description: "Пользователь благодарит"
    priority: 50
    conditions:
      - field: "dialog_analysis.is_gratitude"
        operator: "eq"
        value: true
    actions:
      set_state: "RESOLVED"
      reset_attempts: true

  # === DEFAULT ===
  - id: "default"
    description: "Обычный режим"
    priority: 0
    conditions: []  # Всегда true
    actions:
      set_state: "INITIAL"

# Маппинг состояний на промпты и поведение
states:
  INITIAL:
    prompt_key: "DEFAULT"
    allow_auto_reply: true
    
  CLARIFY:
    prompt_key: "CLARIFY"
    allow_auto_reply: true
    add_clarifying_question: true
    
  LOW_CONFIDENCE:
    prompt_key: "UNCERTAIN"
    allow_auto_reply: true
    suggest_alternatives: true
    
  EMPATHY_MODE:
    prompt_key: "EMPATHY"
    allow_auto_reply: true
    
  REPEATED_ISSUE:
    prompt_key: "SORRY_REPEAT"
    allow_auto_reply: true
    offer_handoff: true
    
  STUCK_LOOP:
    prompt_key: "SUGGEST_HANDOFF"
    allow_auto_reply: false
    force_handoff_option: true
    
  ESCALATE:
    prompt_key: "HANDOFF"
    allow_auto_reply: false
    
  RESOLVED:
    prompt_key: "FAREWELL"
    allow_auto_reply: true
    
  BLOCKED:
    prompt_key: "BLOCKED"
    allow_auto_reply: false
```

**Rule Engine (простая реализация):**

```python
class RuleEngine:
    def __init__(self, rules_path: str):
        self.rules = load_yaml(rules_path)["rules"]
        # Сортируем по priority (desc)
        self.rules.sort(key=lambda r: r.get("priority", 0), reverse=True)
        
    def evaluate(self, state: dict) -> dict:
        for rule in self.rules:
            if self._check_conditions(rule["conditions"], state):
                return self._apply_actions(rule["actions"], state)
        return {"dialog_state": "INITIAL"}
        
    def _check_conditions(self, conditions, state) -> bool:
        for cond in conditions:
            value = self._get_nested(state, cond["field"])
            if not self._compare(value, cond["operator"], cond["value"]):
                return False
        return True
        
    def _compare(self, actual, operator, expected) -> bool:
        ops = {
            "eq": lambda a, e: a == e,
            "ne": lambda a, e: a != e,
            "lt": lambda a, e: a < e,
            "lte": lambda a, e: a <= e,
            "gt": lambda a, e: a > e,
            "gte": lambda a, e: a >= e,
            "in": lambda a, e: a in e,
        }
        return ops[operator](actual, expected)
```

---

### Задача 13: Детекция языка

`langdetect` уже есть в requirements.txt.

**Где определять:**
- В `session_starter` или `aggregate` — сразу после получения вопроса

**Файл:** `app/nodes/_shared_config/languages.yaml`

```yaml
version: "1.0"

detection:
  enabled: true
  library: "langdetect"
  min_text_length: 10  # Для коротких текстов использовать default
  
response:
  strategy: "match_query"  # match_query | user_preference | default
  default_language: "ru"
  
supported:
  - code: "ru"
    name: "Русский"
    greeting: "Здравствуйте!"
  - code: "en"
    name: "English"
    greeting: "Hello!"
```

**Изменения в generation:**
- Добавить в state: `detected_language`
- В system prompt: `"Отвечай на языке: {detected_language}"`

---

## ⚙️ Технические нюансы

### Миграция pipeline_config.json → YAML

**Шаги:**
1. Создать `pipeline_config.yaml` с новой схемой
2. Обновить `app/pipeline/graph.py`:
   ```python
   # Было:
   with open("pipeline_config.json") as f:
       config = json.load(f)
   
   # Станет:
   import yaml
   with open("pipeline_config.yaml") as f:
       config = yaml.safe_load(f)
   ```
3. Тестировать что pipeline работает
4. Удалить `pipeline_config.json`

### Загрузка конфигов нод

**Создать:** `app/services/config_loader/loader.py`

```python
import yaml
from pathlib import Path
from functools import lru_cache

NODES_DIR = Path(__file__).parent.parent.parent / "nodes"

@lru_cache(maxsize=32)
def load_node_config(node_name: str) -> dict:
    """Загрузить конфиг ноды с кэшированием."""
    config_path = NODES_DIR / node_name / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f)

def get_param(node_name: str, param_path: str, default=None):
    """
    Получить параметр с поддержкой вложенности.
    Пример: get_param("rerank", "parameters.top_k", 5)
    """
    config = load_node_config(node_name)
    keys = param_path.split(".")
    value = config
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
    return value if value is not None else default
```

### Валидация конфигов

**Создать:** Pydantic модели для валидации

```python
# app/services/config_loader/schemas.py
from pydantic import BaseModel

class NodeMeta(BaseModel):
    name: str
    version: str = "1.0.0"
    enabled: bool = True

class NodeConfig(BaseModel):
    node: NodeMeta
    parameters: dict = {}
```

### Docker: Перезагрузка конфигов

При изменении YAML файлов нужно:
1. **Dev:** Volumes монтируют локальные файлы → изменения применяются сразу
2. **Prod:** Rebuild контейнера или endpoint для hot-reload

```yaml
# docker-compose.yml (dev)
services:
  api:
    volumes:
      - ./app:/app/app  # Монтируем для hot-reload конфигов
```

---

## ✅ Критерии готовности (Definition of Done)

### Фаза 0: Подготовка
- [ ] PyYAML в requirements.txt
- [ ] `config_loader` сервис работает
- [ ] `_shared_config/` директория создана

### Фаза 1: Миграция на YAML
- [ ] `pipeline_config.yaml` создан и валиден
- [ ] `graph.py` читает YAML
- [ ] Все ноды имеют `config.yaml` (хотя бы шаблоны)
- [ ] Pipeline запускается без ошибок
- [ ] `pipeline_config.json` удалён

### Фаза 2: Критические исправления
- [ ] Грязные сообщения НЕ попадают в историю
- [ ] Telegram бот получает фразы через API
- [ ] Порядок нод: `rerank → multihop`
- [ ] Multihop отдаёт 3+ документа
- [ ] Prompt Routing показывает реальную историю

### Фаза 3: Intent Registry
- [ ] `IntentRegistryService` работает
- [ ] `scripts/refresh_intents.py` успешно выполняется
- [ ] Классификатор использует категории из registry
- [ ] Новая категория в БД → доступна для классификации

### Фаза 4: State Machine
- [ ] `rules.yaml` с 10+ правилами
- [ ] Rule Engine корректно применяет правила
- [ ] Состояния влияют на промпты
- [ ] Добавление правила не требует изменения кода

### Фаза 5: Улучшения
- [ ] LLM Aggregation работает при включении
- [ ] Lightweight берёт N последних сообщений
- [ ] Ответ на языке вопроса
- [ ] `build_config.py` генерирует единый конфиг

---

## 📎 Приложения

### Чеклист для каждой ноды

```
[ ] config.yaml создан
[ ] Параметры вынесены из кода
[ ] Нода читает из config.yaml
[ ] Дефолтные значения в коде (fallback)
[ ] Документация в meta секции
```

### Команды

```bash
# Обновить реестр интентов
python scripts/refresh_intents.py

# Собрать единый конфиг
python scripts/build_config.py

# Валидировать все конфиги
python scripts/validate_configs.py
```

---

*Документ будет обновляться по мере реализации.*
