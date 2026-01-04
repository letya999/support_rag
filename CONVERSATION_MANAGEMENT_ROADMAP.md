# MVP RAG Support Engine + Conversation Management

Полнофункциональный RAG движок для поддержки с управлением диалогами, персистентной памятью и интеллектуальной эскалацией.

---

## Архитектура

### Core Stack
- **Оркестрация**: LangGraph (параллельные ветки для RAG + State Machine)
- **Хранилище векторов**: Qdrant + PostgreSQL (pgvector)
- **Кеш**: Redis (FAQ кеш + сессии)
- **Персистентность**: PostgreSQL (архив сессий, профили юзеров, эскалации)
- **LLM**: OpenAI (или совместимое)
- **Мониторинг**: Langfuse (трейсинг всех шагов)

### Принцип работы
1. Пользователь пишет сообщение
2. **Параллельно** запускаются: RAG pipeline + State Machine analysis
3. RAG: retrieval + ranking → generation
4. State Machine: анализ диалога, определение состояния
5. Prompt Router выбирает правильный промпт в зависимости от состояния
6. LLM генерирует ответ
7. Emotion Detector проверяет злость/фрустрацию юзера
8. Escalation Decision собирает все сигналы и решает: ответить или передать на человека
9. Результат либо кешируется и отправляется юзеру, либо готовится к передаче специалисту
10. Session архивируется в Postgres для долгосрочной памяти

---

## Компоненты системы

### 1. Конфигурация и персистентность

#### Config System (`app/config/conversation_config.py`)
Единый источник параметров:
- **Aggregation**: сколько сообщений брать, извлекать ли сущности
- **Session**: TTL сессии, timeout неактивности, что считать новой сессией
- **Escalation**: макс попыток, threshold уверенности, threshold эмоций
- **Clarification**: включена ли, в каком range уверенности
- **Response**: макс токенов в ответе
- **Persistence**: сохранять ли в Postgres, суммаризировать ли при эскалации
- **A/B Testing**: какой вариант aggregation использовать

#### Postgres Schema
```
sessions_archive          - архив завершенных сессий
session_summaries         - поисковые резюме для контекста
user_profiles             - долгосрочная память о юзерах
escalations               - отдельная история эскалаций
```

#### Redis Extensions
Расширить `UserSession`:
- `current_problem` - о чем сейчас спрашивает
- `dialog_state` - текущее состояние диалога
- `attempt_count` - попыток решить текущую проблему
- `last_answer_confidence` - уверенность последнего ответа
- `last_emotion_detected` - эмоции из последнего сообщения
- `extracted_entities` - кешированные сущности

---

### 2. RAG Pipeline (параллельная ветка)

#### Lightweight Conversation Aggregator (основной)
Без LLM вызовов, чистый Python:
- Фильтрует только user сообщения (убирает bot ответы)
- Извлекает сущности regex + heuristics: номера, ID заказов, даты, ключевые слова
- Детектит контекстные ссылки ("а что с тем номером что я давал")
- Строит компактный query для retrieval (убирает шум)
- **Скорость**: <50ms, бесплатно

#### LLM Conversation Aggregator (вариант для тестирования)
Для сложных многошаговых диалогов:
- Вызывает LLM если сообщений много или entities сложные
- Выбирается условно для A/B теста
- Fallback для случаев когда lightweight не справляется
- **Скорость**: +200-300ms, +$0.0001

#### Выбор варианта
Динамически при инициализации графа в зависимости от config флага `use_llm_aggregation`

#### Классификация + Поиск
- FastText классификатор (intent/category)
- Гибридный поиск (vector + lexical)
- Reranking (cross-encoder)
- Получение контекста для generation

---

### 3. State Machine (параллельная ветка)

#### Dialog State Analyzer
Анализирует последние сообщения (БЕЗ API):
- Ищет сигналы: благодарность, просьба на escalation, вопросы, фрустрация
- Проверяет повторяемость вопроса
- Детектит новую conversation если прошло времени
- Результат - набор boolean флагов и сигналов

#### Session State Updater
Детерминированная state machine (на основе сигналов и RAG результатов):
- Если юзер явно попросил человека → ESCALATION_REQUESTED
- Если спасибо → RESOLVED
- Если low confidence + много попыток → ESCALATION_NEEDED
- Если повтор вопроса → ANSWER_PROVIDED (increment attempt_count)
- Иначе → ANSWER_PROVIDED (default)

Обновляет session data в Redis

---

### 4. Prompt Routing

#### Prompt Router Node
На основе `dialog_state` выбирает правильный system prompt:
- **INITIAL**: "Помогите четко и кратко"
- **ANSWER_PROVIDED** (повторная попытка): "Уже ответили, дайте НОВУЮ информацию или уточните"
- **AWAITING_CLARIFICATION**: "Пользователь ответил на уточнение, решите проблему"
- **RESOLVED**: "Юзер доволен, предложите дополнительную помощь"
- **ESCALATION_NEEDED**: "Передавайте на человека, будьте эмпатичны"
- **ESCALATION_REQUESTED**: "Юзер хочет человека, не сопротивляйтесь"

Обогащает промпт:
- Контекст из истории (последние 2-3 сообщения)
- Извлеченные сущности (номера, даты, ID)
- Информация из долгосрочной памяти юзера (если есть)

---

### 5. Generation и Safety

#### Enhanced Generation Node
- Использует подготовленный system_prompt из Router
- Генерирует ответ на основе: prompt + question + retrieved docs
- Возвращает ответ + метаданные (модель, токены)

#### Emotion & Sentiment Detector (ПОСТГЕНЕРАЦИОННЫЙ)
После того как сгенерировали ответ, проверяем эмоции:
- Text signals: заглавные буквы, пунктуация, отрицательные слова
- Behavioral signals: длина сообщения, повторяемость
- Optional: легкий классификатор (distilBERT local)
- Output: sentiment (angry/frustrated/neutral/satisfied), confidence, severity score

**Почему после generation**: видим полный контекст, можем скорректировать перед отправкой

#### Response Validator (опциональный)
- Проверяет groundedness (ответ из docs?)
- Проверяет completeness (адресуется ли вопрос?)
- Проверяет format (нет плейсхолдеров?)

---

### 6. Escalation Logic

#### Escalation Decision Node
Собирает ВСЕ сигналы и решает finalize:

1. **Явная просьба** (`user_requested_escalation`) → ESCALATE
2. **Невалидный ответ** (validation errors) → ESCALATE
3. **Злой юзер** (`sentiment.severity > 0.8`) → ESCALATE
4. **Категория/интент = "forbidden"** (в metadata/config) → ESCALATE
5. **Low confidence + много попыток** (`confidence < 0.5 AND attempt_count >= 3`) → ESCALATE
6. **State machine решил** (`dialog_state == ESCALATION_NEEDED`) → ESCALATE
7. **Иначе** → AUTO_REPLY

Output: `escalation_decision` ("escalate" | "auto_reply") + `escalation_reason` + `escalation_priority`

#### Escalation Handoff Node
Подготавливает сессию к передаче:
- Генерирует краткое резюме (проблема, что пробовали, почему escalate)
- Собирает контекст: полная история + сущности + профиль юзера
- Форматирует для специалиста (timeline, цветная разметка, флаги)

#### Route to Specialist Node
- Отправляет handoff package в систему специалистов (Telegram, Zendesk, etc)
- Создает escalation record в Postgres
- Возвращает статус и info для юзера

---

### 7. Storage & Persistence

#### Cache Storage
Кеширует в Redis только успешные AUTO_REPLY ответы (не escalations):
- Query + answer + confidence + docs + timestamp

#### Session Archive
Когда сессия завершена (RESOLVED или ESCALATED):
- Архивирует в `sessions_archive` (метрики, duration, outcome)
- Создает запись в `session_summaries` (резюме + теги для поиска)
- Обновляет/создает `user_profiles` (долгосрочная память)
- Если escalation - создает запись в `escalations`

---

## График реализации

### Этап 1: Foundation (2-3 ч)
- [x] Config system + Postgres schema + миграции
- [x] Расширить Redis UserSession
- [x] Загрузка долгосрочной памяти при старте сессии

### Этап 2: RAG Enhancement (2-3 ч)
- [x] Lightweight aggregator node
- [x] LLM aggregator node (вариант)
- [x] Интеграция с существующим pipeline

### Этап 3: State Machine (2 ч)
- [x] Dialog analyzer node
- [x] Session state updater node
- [x] Перестройка графа на параллельные ветки

### Этап 4: Prompt Routing (1.5 ч)
- [x] Prompt router node
- [x] Модифицировать generation на использование routed prompts
- [x] State-aware промпты

### Этап 5: Safety & Emotion (1.5 ч)
- [ ] Emotion detector node
- [ ] Response validator node (опциональный)

### Этап 6: Escalation (2 ч)
- [ ] Escalation decision node
- [ ] Escalation handoff node
- [ ] Route to specialist node

### Этап 7: Persistence (1-2 ч)
- [ ] Archive session logic
- [ ] Update user profile logic
- [ ] Escalation records

### Этап 8: Integration & Testing (2-3 ч)
- [ ] Unit tests для каждой ноды
- [ ] Integration тесты (full graph)
- [ ] A/B test lightweight vs LLM aggregation
- [ ] Performance profiling

**Total: ~15-17 часов до production-ready MVP**

---

## Конфигурируемые параметры

```yaml
conversation_config:
  # Aggregation
  aggregation_max_messages: 6
  extract_entities_enabled: true
  use_llm_aggregation: false  # для A/B теста

  # Session management
  session_ttl_hours: 24
  session_timeout_minutes: 30
  session_idle_threshold_minutes: 5

  # Escalation logic
  max_attempts_before_escalation: 3
  escalation_confidence_threshold: 0.5
  sentiment_escalation_threshold: 0.8

  # Clarification
  clarification_enabled: true
  clarification_confidence_range: [0.3, 0.6]

  # Response
  max_response_tokens: 500

  # Persistence
  persist_to_postgres: true
  summarize_on_escalation: true

  # Category/Intent routing
  always_escalate_categories: ["billing_dispute", "account_closure", "complaint"]
  always_escalate_intents: ["urgent", "vip"]
```

---

## LangGraph Flow (высокоуровневое)

```
START
  ↓
Load session + long-term memory
  ↓
Check cache (FAQ hit?)
  ├─ HIT → return cached answer
  └─ MISS
      ↓
      [PARALLEL BRANCHES]
      RAG PIPELINE                STATE MACHINE
      ├─ aggregate (LW or LLM)    ├─ analyze_dialog
      ├─ classify                 └─ update_state
      ├─ search/rank
      └─ prepare context

      ↓ [SYNC]
      route_and_build_prompt
      ↓
      generate_answer
      ↓
      emotion_detect
      ↓
      validate_response
      ↓
      escalation_decision
      ├─ AUTO_REPLY
      │  ├─ store_cache
      │  ├─ archive_session
      │  └─ send_to_user
      │
      └─ ESCALATE
         ├─ prepare_handoff
         ├─ route_to_specialist
         ├─ create_escalation_record
         └─ send_to_specialist
```

---

## State (TypedDict)

Единая структура для всех нод:

```
Input:
  question: str
  conversation_history: List[dict]
  conversation_config: dict

From Aggregation:
  aggregated_query: str
  extracted_entities: dict

From RAG:
  docs: List[str]
  confidence: float

From State Machine:
  dialog_state: str
  attempt_count: int
  dialog_analysis: dict

From Prompt Router:
  system_prompt: str
  generation_strategy: str

From Generation:
  answer: str

From Emotion:
  sentiment_analysis: dict

From Validation:
  validation_errors: List[str]

From Escalation:
  escalation_decision: str
  escalation_reason: str
  escalation_priority: str

Metadata:
  query_id: str
  session_id: str
  user_id: int
  timestamp: str
```

---

## Узлы графа

| Узел | Тип | Параллель | API вызовы | Критичный |
|------|-----|-----------|-----------|-----------|
| aggregate_lightweight | Processing | Да | Нет | Да |
| aggregate_with_llm | Processing | Да | LLM | Нет |
| analyze_dialog | Processing | Да | Нет | Да |
| update_session | Processing | Да | Нет | Да |
| classify/search/rank | Processing | Да | Models | Да |
| route_prompt | Processing | Нет | Нет | Да |
| generate | Processing | Нет | LLM | Да |
| emotion_detect | Processing | Нет | Optional ML | Да |
| validate_response | Processing | Нет | Нет | Нет |
| escalation_decision | Conditional | Нет | Нет | Да |
| prepare_handoff | Processing | Нет | Optional LLM | Нет |
| route_specialist | Processing | Нет | Specialist API | Нет |
| store_cache | Processing | Нет | Redis | Нет |
| archive_session | Processing | Нет | Postgres | Нет |

---

## Особенности MVP

✅ **Lightweight aggregation** - быстрая экстракция фактов без LLM
✅ **A/B testing** - можно сравнить LW vs LLM aggregation
✅ **Параллельная обработка** - RAG + State Machine одновременно
✅ **Emotion-aware** - детектирует злого юзера ДО отправки ответа
✅ **Многоуровневая эскалация** - confidence + попытки + эмоции + категория + intent
✅ **Персистентная память** - долгосрочный контекст о юзере
✅ **Кеширование FAQ** - ускорение повторяющихся вопросов
✅ **Полная конфигурируемость** - все параметры через config
✅ **Оси масштабирования** - можно отключать дорогие ноды (LLM aggregation, emotion, validation)

---

## Next Steps

1. Создать feature branch
2. Реализовать в порядке этапов (1-8)
3. Каждый этап = отдельный commit
4. Интегрировать Telegram bot layer на конце
5. Добавить тесты на каждом этапе
