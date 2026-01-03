# 🚀 Roadmap: Многоходовые рассуждения + Кеширование + Telegram интеграция

**Комплексный план развития Support RAG с добавлением Multi-Hop рассуждений, кеширования и интеграции с Telegram.**

---

## 📋 Обзор инициативы

Текущий проект (Этап 4.7): Добавить к существующему RAG пайплайну:
1. **Multi-Hop рассуждения** — поиск цепочек связанных документов для сложных вопросов
2. **Кеширование часто задаваемых вопросов** — быстрые ответы без переобработки
3. **Telegram-интеграция** — диалоговый интерфейс с сохранением контекста
4. **Диалоговая логика** — управление историей, команда `/clear` для очистки контекста

**Общее время реализации:** 10-14 дней

---

## 🎯 ЭТАП 1: Многоходовые рассуждения (Multi-Hop) — 5-6 дней

### 1.1 Архитектура Multi-Hop

```
Вопрос → Детектор сложности →
  ├─ Если простой → обычный поиск (retrieve)
  └─ Если сложный →
      ├─ Первый хоп: поиск топ-1 релевантного документа
      ├─ Граф связей: использование category + intent для нахождения связанных Q&A
      ├─ Второй+ хопы: поиск документов с похожей category или связанной логикой
      └─ Объединение: слияние ответов из всех хопов → генерация
```

**Компоненты:**
- **Complexity Detector** — оценивает сложность вопроса (простой/средний/сложный)
- **Hop Resolver** — управляет циклом поиска по связанным вопросам и слиянием результатов
- **Context Merger** — объединяет ответы из нескольких хопов в единый контекст
- **Relation Builder** — строит граф связей между Q&A на основе существующих метаданных (category, intent)

---

### 1.2 Детектор сложности (`app/nodes/multihop/complexity_detector.py`)

**Логика (Bilingual RU/EN, без LLM вызовов):**

Система анализирует текст на наличие структурных маркеров сложности на обоих языках.

```python
# Наборы маркеров для анализа
MARKERS = {
    "question_words": {
        "en": ["how", "why", "what", "when", "which", "where", "explain", "describe"],
        "ru": ["как", "почему", "зачем", "что", "когда", "какой", "где", "объясни", "опиши"]
    },
    "logical_connectors": {
        "en": ["if", "then", "else", "because", "unless", "provided", "assuming", "after", "before"],
        "ru": ["если", "то", "иначе", "потому", "так как", "хотя", "при условии", "после", "до"]
    },
    "conjunctions": {
        "en": ["and", "or", "also", "with", "besides"],
        "ru": ["и", "или", "также", "с", "кроме"]
    }
}

Алгоритм оценки:
1. Определение языка (Cyrillic vs Latin)
2. Подсчет маркеров для выбранного языка:
   - Каждое уникальное слово из question_words → +1 балл
   - Каждое вхождение logical_connectors → +1.5 балла
   - Каждая конъюнкция (and/or/и/или) → +0.5 балла
3. Анализ структуры:
   - Наличие запятых (признак сложных предложений) → +0.5 балла за каждую
   - Количество слов > 15 → +1 балл
   - Количество слов > 25 → +2 балла

Итоговый маппинг:
  Score < 1.5 → simple (num_hops: 1)
  1.5 <= Score < 3.5 → medium (num_hops: 2)
  Score >= 3.5 → complex (num_hops: 3)
```

**Выход:**
```python
class ComplexityOutput(BaseModel):
    complexity_level: Literal["simple", "medium", "complex"]
    complexity_score: float  # Итоговый балл
    language: Literal["ru", "en"]
    detected_markers: List[str]  # Найденные слова-маркеры
    num_hops: int  # Рекомендуемое количество хопов (1, 2 или 3)
    confidence: float # Уверенность в детекции (напр. на основе длины запроса)
```

---

### 1.3 Resolver хопов (`app/nodes/multihop/hop_resolver.py`)

**Логика:**

```
Hop 0 (первоначальный поиск):
  - Используется исходный вопрос
  - Retrieval обычным способом → top_doc_1
  - Оценка релевантности top_doc_1

Hop 1+ (для сложных вопросов):
  - Извлечение см_also из metadata top_doc_1
  - Построение поисковых запросов для связанных документов
  - Retrieval для каждого связанного документа
  - Фильтрация (оставить > threshold релевантности)
  - Объединение контекста

Stop условия:
  - Найден "базовый" документ (has_complete_answer: true)
  - Выполнены все рекомендуемые хопы
  - Достигнута граница максимум_хопов (обычно 3)
```

**Выход:**
```python
class HopResolverOutput(BaseModel):
    primary_doc: str  # топ-1 документ
    related_docs: List[str]  # документы из хопов
    hop_chain: List[dict]  # детали каждого хопа
    merged_context: str  # объединенный контекст
    total_hops_performed: int
    retrieval_time: float
    confidence: float  # средняя релевантность
```

---

### 1.4 Граф связей (`app/nodes/multihop/relation_builder.py`)

**Цель:** Управление связями между Q&A документами на основе существующей структуры

```python
# Используемая структура (БЕЗ ИЗМЕНЕНИЙ):
{
  "question": "How do I reset my password?",
  "answer": "You can reset your password by clicking on the 'Forgot Password' link...",
  "metadata": {
    "category": "Account Access",
    "intent": "reset_password",
    "requires_handoff": false,
    "confidence_threshold": 0.9,
    "clarifying_questions": [
        "Do you have access to the email address associated with your account?"
    ]
  }
}

# Граф связей (строится в памяти на основе existing metadata):
{
  "doc_123": {
    "same_category": ["doc_456", "doc_789"],  # те же category
    "same_intent": ["doc_111"],  # те же intent
    "related_intents": ["doc_222"],  # логически связанные intents
    "clarifying_topics": ["doc_333"],  # из clarifying_questions
  }
}

# Правила связей:
- same_category: все Q&A с category == "Account Access"
- same_intent: все Q&A с intent == "reset_password"
- related_intents: "reset_password" связан с "contact_support", "view_history"
- clarifying_topics: вопросы из clarifying_questions указывают на связанные документы
```

**Функции:**
- `build_relation_graph(documents)` — построить граф при загрузке (один раз)
- `find_related_docs(doc_index, query)` — найти связанные документы по category/intent
- `rank_relations(related_docs, query)` — ранжировать по релевантности к запросу

---

### 1.5 Слияние ответов (`app/nodes/multihop/context_merger.py`)

**Логика слияния ответов из нескольких связанных Q&A:**

```python
Алгоритм:
1. Упорядочить найденные Q&A по релевантности (rerank_scores)
2. Объединить ответы в порядке релевантности:
   - Primary answer (из основного вопроса) — 100%
   - Hop 1 answers (из категории или intent) — ранжированы
   - Hop 2+ answers (если есть место в контексте)
3. Убрать дублирование контента (одинаковые ответы)
4. Добавить разделители и источники:
   ### Основной ответ
   [answer_1]

   ### Дополнительная информация (Category: Account Access)
   [answer_2]

   ### Связанный вопрос
   [answer_3]

5. Обеспечить, чтобы общая длина контекста < max_tokens (5000 tokens)

Стратегия обрезки при переполнении:
  - Если merged_context > max_tokens:
    - Обрезать менее релевантные хопы (начиная с hop 2+)
    - Сохранить primary answer (обязателен)
```

**Выход:**
```python
class MergedContext(BaseModel):
    combined_text: str
    qa_sources: List[{
        "question": str,
        "hop_level": int,
        "score": float,
        "category": str
    }]
    total_tokens: int
    truncated: bool
```

---

### 1.6 Интеграция в пайплайн

**Расположение в `app/pipeline/state.py`:**

```python
# Добавить поля:
complexity_level: Optional[Literal["simple", "medium", "complex"]]
complexity_score: Optional[float]
num_hops_required: Optional[int]

# Multi-hop
primary_doc: Optional[str]
related_docs: List[str]
hop_chain: Optional[List[dict]]
merged_context: Optional[str]
multihop_used: Optional[bool]
hops_performed: Optional[int]
```

**Обновление `app/pipeline/graph.py`:**

```
Условная логика (после retrieve, перед generate):
  if complexity_level == "simple":
    → пропустить multihop → generate
  else:
    → multihop_resolver → generate
```

**Node в graph:**
```
classify → metadata_filter → retrieve →
  [complexity_detection (встроено в retrieve)] →
  [conditional: complexity == simple? yes→generate : no→multihop] →
  multihop → merge_context → generate → route
```

---

### 1.7 Файлы для создания (Этап 1)

```
app/nodes/multihop/
├── __init__.py
├── complexity_detector.py      # ComplexityDetector класс
├── hop_resolver.py             # HopResolver класс
├── relation_graph.py           # RelationGraphBuilder класс
├── context_merger.py           # ContextMerger класс
├── models.py                   # Pydantic модели для вывода
├── node.py                     # Обёртка LangGraph узла
└── prompts.py                  # Шаблоны запросов (если нужны)
```

---

### 📌 ВАЖНО: Структура данных НЕ меняется

Multi-hop работает с существующей структурой Q&A JSON **без её изменения**:

```json
{
  "question": "How do I reset my password?",
  "answer": "You can reset your password by clicking on the 'Forgot Password' link...",
  "metadata": {
    "category": "Account Access",
    "intent": "reset_password",
    "requires_handoff": false,
    "confidence_threshold": 0.9,
    "clarifying_questions": ["Do you have access to the email...?"]
  }
}
```

**Как multi-hop находит связи:**
1. **Hop 0 (первичный):** Вопрос "Why can't I reset if I forgot email?" → найти primary Q&A (reset_password)
2. **Hop 1:** Из primary найти все Q&A с категорией "Account Access" → найти Q&A про восстановление email
3. **Hop 2:** Из найденных Q&A использовать их clarifying_questions для поиска дополнительных связей
4. **Merge:** Объединить ответы в единый контекст → передать в generation

**Граф строится динамически**, без добавления новых полей в JSON.

---

## 🎯 ЭТАП 2: Кеширование часто задаваемых вопросов — 3-4 дня

### 2.1 Архитектура кеширования

```
Вопрос → Нормализация → Хеширование →
  ├─ Найден в кэше → вернуть кэшированный ответ
  └─ Не найден → полный пайплайн → сохранить в кэш
```

**Компоненты:**
- **Query Normalizer** — нормализирует вопрос (удаляет пунктуацию, приводит в нижний случай и т.д.)
- **Cache Layer** — хранит часто задаваемые вопросы и ответы
- **Cache Manager** — управляет LRU или TTL кэшем
- **Analytics** — отслеживает hit rate кэша

---

### 2.2 Query Normalizer (`app/cache/query_normalizer.py`)

**Логика нормализации (Bilingual RU/EN):**

```python
def normalize_query(query: str) -> str:
    """
    Приводит разные формулировки одного вопроса к одной форме.

    Примеры:
    - "How to reset password?" → "reset password"
    - "Как сбросить пароль?" → "сбросить пароль"
    - "how reset my password?" → "reset password"
    - "Reset password, please" → "reset password"
    """

    steps:
    1. Приведение к нижнему регистру
    2. Удаление пунктуации (?, !, ., ,)
    3. Удаление стоп-слов (Bilingual: how, what, can, do, please, как, что, можно, ли, пожалуйста)
    4. Удаление дублирующиеся пробелов
    5. Сортировка ключевых слов (для "reset password" и "password reset" → одно и то же)

    Результат: "reset password" или "сбросить пароль"
```

---

### 2.3 Cache Layer (`app/cache/cache_layer.py`)

**Технология:** Redis (если доступен) или в памяти (для dev)

**Структура:**

```python
class CacheEntry(BaseModel):
    query_normalized: str
    query_original: str
    answer: str
    doc_ids: List[str]  # какие документы использовались
    confidence: float
    timestamp: datetime
    hit_count: int = 0  # сколько раз был использован
    user_rating: Optional[float] = None  # если пользователь оценил ответ

class CacheManager:
    # LRU кэш в памяти
    cache: Dict[str, CacheEntry]
    max_cache_size: int = 1000  # максимум записей
    ttl_seconds: int = 3600 * 24  # 24 часа

    def get(query: str) -> Optional[CacheEntry]
    def set(query: str, answer: str, docs: List[str], confidence: float)
    def delete(query: str)
    def clear_expired()
    def get_stats() -> CacheStats
```

---

### 2.4 Cache Statistics (`app/cache/cache_stats.py`)

**Отслеживаемые метрики:**

```python
class CacheStats(BaseModel):
    total_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float  # hits / (hits + misses)
    avg_response_time_cached: float  # мс
    avg_response_time_full: float  # мс
    savings_time: float  # total_time_saved в секундах
    memory_usage: float  # KB
    most_asked_questions: List[str]  # top 5
```

---

### 2.5 Интеграция в пайплайн

**Расположение в `app/pipeline/state.py`:**

```python
cache_hit: Optional[bool]
cache_key: Optional[str]
```

**Обновление graph.py:**

```
START → check_cache →
  ├─ cache_hit: true → return_cached_answer → END
  └─ cache_hit: false → classify → ... → generate → store_in_cache → END
```

**Node-обёртки:**

```python
# app/cache/nodes.py
async def check_cache_node(state: State) -> State
async def store_in_cache_node(state: State) -> State
```

---

### 2.6 Файлы для создания (Этап 2)

```
app/cache/
├── __init__.py
├── query_normalizer.py      # QueryNormalizer класс
├── cache_layer.py           # CacheManager класс
├── cache_stats.py           # CacheStats и мониторинг
├── models.py                # Pydantic модели
└── nodes.py                 # LangGraph узлы (check_cache, store_cache)
```

---

## 🎯 ЭТАП 3: Telegram интеграция — 4-5 дней

### 3.1 Архитектура Telegram бота

```
Telegram User →
  /start → initialize session
  /ask "вопрос" → process_query (с контекстом диалога)
  /clear → clear_context
  /history → show_conversation
  /rate ⭐⭐⭐⭐⭐ → feedback
  /settings → user_settings
```

**Компоненты:**
- **Session Manager** — управляет сессией пользователя, контекстом
- **Dialog Manager** — управляет логикой диалога и историей
- **Telegram Bot Handler** — обработчик сообщений
- **Context Store** — хранит контекст разговора (в Redis или PostgreSQL)

---

### 3.2 Session Manager (`app/integrations/telegram/session_manager.py`)

**Структура:**

```python
class UserSession(BaseModel):
    user_id: int  # Telegram user_id
    username: str
    conversation_history: List[Message]  # история диалога
    context: Dict[str, Any]  # контекст (текущий интент, category и т.д.)
    created_at: datetime
    last_updated: datetime
    preferences: UserPreferences  # язык, стиль ответов и т.д.

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime
    query_id: Optional[str]  # для связи с пайплайном

class UserPreferences(BaseModel):
    language: str = "ru"
    include_sources: bool = True
    response_format: Literal["short", "detailed"] = "detailed"
```

**Функции:**

```python
class SessionManager:
    def create_session(user_id: int, username: str) -> UserSession
    async def get_session(user_id: int) -> Optional[UserSession]
    async def update_session(user_id: int, **updates)
    async def add_message(user_id: int, role: str, content: str)
    async def clear_history(user_id: int)
    async def get_context(user_id: int) -> Dict
    async def set_context(user_id: int, **context_data)
    async def delete_session(user_id: int)  # на требование пользователя
```

---

### 3.3 Dialog Manager (`app/integrations/telegram/dialog_manager.py`)

**Логика диалога с поддержкой контекста:**

```python
class DialogManager:
    """
    Управляет логикой диалога с учётом истории и контекста.
    """

    async def process_query(
        user_id: int,
        query: str
    ) -> DialogResponse:
        """
        Обработка вопроса с контекстом сессии.
        """

        steps:
        1. Получить UserSession
        2. Добавить query в conversation_history
        3. Определить, related ли query к предыдущему контексту
           - Если related: передать context в пайплайн
           - Если новый топик: reset context
        4. Запустить RAG пайплайн (с context)
        5. Получить response от пайплайна
        6. Добавить response в conversation_history
        7. Обновить context для следующего query
        8. Вернуть DialogResponse (ответ + метаданные)

        Пример контекста:
        {
            "current_intent": "reset_password",
            "category": "Account Access",
            "hop_level": 1,  # сложность предыдущего вопроса
        }

        Если новый вопрос касается другого интента:
        → сбросить старый контекст (кроме истории)
```

**Выход:**

```python
class DialogResponse(BaseModel):
    answer: str
    sources: List[{"title": str, "doc_id": str}]
    confidence: float
    followup_questions: Optional[List[str]]  # предложить уточняющие вопросы
    user_rating_prompt: bool = True  # предложить оценить ответ
```

---

### 3.4 Telegram Bot Handler (`app/integrations/telegram/bot_handler.py`)

**Структура команд:**

```python
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

class TelegramBotHandler:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        """
        Регистрация обработчиков команд и сообщений.
        """

        # Команды
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("ask", self.cmd_ask))
        self.app.add_handler(CommandHandler("clear", self.cmd_clear))
        self.app.add_handler(CommandHandler("history", self.cmd_history))
        self.app.add_handler(CommandHandler("rate", self.cmd_rate))
        self.app.add_handler(CommandHandler("settings", self.cmd_settings))

        # Обработка обычных сообщений
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        # Обработка callbacks (кнопки)
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /start — инициализировать сессию пользователя.
        """
        user_id = update.effective_user.id
        username = update.effective_user.username

        session = await session_manager.create_session(user_id, username)

        text = f"""
        👋 Добро пожаловать, {username}!

        Это Support RAG бот. Вот что я могу делать:

        /ask "вопрос" — задать вопрос
        /clear — очистить историю диалога
        /history — показать историю
        /rate ⭐ — оценить ответ
        /settings — настройки

        Или просто напишите вопрос сообщением!
        """

        await update.message.reply_text(text)

    async def cmd_ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /ask "вопрос" — задать вопрос с аргументом.
        """
        user_id = update.effective_user.id

        if not context.args:
            await update.message.reply_text(
                "⚠️ Использование: /ask \"ваш вопрос\""
            )
            return

        query = " ".join(context.args)
        await self._process_and_respond(update, user_id, query)

    async def cmd_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /clear — очистить контекст диалога и историю.
        """
        user_id = update.effective_user.id

        # Подтверждение перед очисткой
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, очистить", callback_data="clear_confirm"),
                InlineKeyboardButton("❌ Отмена", callback_data="clear_cancel")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚠️ Вы уверены? Это удалит всю историю.",
            reply_markup=reply_markup
        )

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /history — показать историю последних 10 сообщений.
        """
        user_id = update.effective_user.id
        session = await session_manager.get_session(user_id)

        if not session or len(session.conversation_history) == 0:
            await update.message.reply_text("📝 История пуста.")
            return

        # Последние 10 сообщений
        messages = session.conversation_history[-10:]
        text = "📝 История диалога (последние 10):\n\n"

        for msg in messages:
            role_emoji = "👤" if msg.role == "user" else "🤖"
            text += f"{role_emoji} {msg.content[:100]}...\n"

        await update.message.reply_text(text)

    async def cmd_rate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /rate ⭐⭐⭐⭐ — оценить последний ответ.
        """
        user_id = update.effective_user.id

        if not context.args:
            await update.message.reply_text(
                "⚠️ Использование: /rate ⭐⭐⭐⭐"
            )
            return

        rating_str = context.args[0]
        rating = rating_str.count('⭐')  # количество звёзд

        if rating < 1 or rating > 5:
            await update.message.reply_text(
                "⚠️ Оценка от 1⭐ до 5⭐"
            )
            return

        # Найти последний ответ бота
        session = await session_manager.get_session(user_id)
        if not session.conversation_history:
            await update.message.reply_text("📝 Нечего оценивать.")
            return

        # Сохранить рейтинг
        await feedback_store.save_rating(
            user_id=user_id,
            query=session.conversation_history[-2].content,  # предпоследнее (вопрос)
            answer=session.conversation_history[-1].content,  # последнее (ответ)
            rating=rating
        )

        await update.message.reply_text(f"✅ Спасибо! Вы оценили на {rating_str}")

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /settings — управление настройками.
        """
        user_id = update.effective_user.id
        session = await session_manager.get_session(user_id)

        keyboard = [
            [InlineKeyboardButton("🌍 Язык", callback_data="settings_language")],
            [InlineKeyboardButton("📋 Длина ответа", callback_data="settings_response_format")],
            [InlineKeyboardButton("🔗 Источники", callback_data="settings_sources")],
            [InlineKeyboardButton("❌ Закрыть", callback_data="settings_close")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚙️ Настройки:",
            reply_markup=reply_markup
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработка обычного текстового сообщения.
        Пользователь просто пишет вопрос.
        """
        user_id = update.effective_user.id
        query = update.message.text

        await self._process_and_respond(update, user_id, query)

    async def _process_and_respond(
        self,
        update: Update,
        user_id: int,
        query: str
    ):
        """
        Основная логика обработки вопроса.
        """
        # Показать индикатор печати
        async with update.message.chat.action(ChatAction.TYPING):
            try:
                # Обработать через dialog_manager
                dialog_response = await dialog_manager.process_query(user_id, query)

                # Форматировать ответ
                response_text = f"""
🤖 {dialog_response.answer}

**Источники:**
"""
                for src in dialog_response.sources:
                    response_text += f"- [{src['title']}]"

                response_text += f"\n\nДоверие: {dialog_response.confidence:.0%}"

                # Отправить ответ
                await update.message.reply_text(response_text, parse_mode="Markdown")

                # Предложить оценить (если нужно)
                if dialog_response.user_rating_prompt:
                    keyboard = [
                        [
                            InlineKeyboardButton("⭐", callback_data="rate_1"),
                            InlineKeyboardButton("⭐⭐", callback_data="rate_2"),
                            InlineKeyboardButton("⭐⭐⭐", callback_data="rate_3"),
                            InlineKeyboardButton("⭐⭐⭐⭐", callback_data="rate_4"),
                            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="rate_5"),
                        ]
                    ]

                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(
                        "Оцените ответ:",
                        reply_markup=reply_markup
                    )

                # Предложить уточняющие вопросы
                if dialog_response.followup_questions:
                    text = "Может быть, вас интересует:\n"
                    for i, q in enumerate(dialog_response.followup_questions[:3]):
                        text += f"{i+1}. {q}\n"
                    await update.message.reply_text(text)

            except Exception as e:
                logger.error(f"Error processing query: {e}")
                await update.message.reply_text(
                    "❌ Произошла ошибка. Попробуйте позже."
                )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработка нажатий на кнопки (inline keyboard).
        """
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id

        if query.data == "clear_confirm":
            await session_manager.clear_history(user_id)
            await query.edit_message_text("✅ История очищена.")

        elif query.data == "clear_cancel":
            await query.edit_message_text("❌ Отменено.")

        elif query.data.startswith("rate_"):
            rating = int(query.data.split("_")[1])
            await feedback_store.save_rating(user_id, rating)
            await query.edit_message_text(f"✅ Спасибо! Вы оценили на {'⭐' * rating}")

        elif query.data.startswith("settings_"):
            # Обработка настроек
            await self._handle_settings_callback(query, user_id, query.data)

    def start(self):
        """Запустить бота."""
        self.app.run_polling()
```

---

### 3.5 Context Store (`app/integrations/telegram/context_store.py`)

**Технология:** Redis (production) или PostgreSQL (fallback)

```python
class ContextStore:
    """
    Постоянное хранилище сессий пользователей.
    """

    async def save_session(user_id: int, session: UserSession)
    async def load_session(user_id: int) -> Optional[UserSession]
    async def delete_session(user_id: int)
    async def update_message_history(user_id: int, message: Message)
    async def get_recent_messages(user_id: int, limit: int = 10) -> List[Message]
    async def prune_old_sessions(days: int = 30)  # удалить старые сессии
```

---

### 3.6 Интеграция в пайплайн

**Вызов пайплайна из Telegram:**

```python
async def process_query(user_id: int, query: str) -> DialogResponse:
    """
    Запуск RAG пайплайна с контекстом сессии.
    """

    session = await session_manager.get_session(user_id)

    # Подготовить input для пайплайна
    input_state = {
        "question": query,
        "user_id": user_id,
        "conversation_context": session.context,  # передать контекст
    }

    # Запустить пайплайн
    result = await rag_graph.ainvoke(input_state)

    # Извлечь результат
    answer = result.get("answer", "")
    confidence = result.get("confidence", 0)
    sources = result.get("best_doc_metadata", {})

    return DialogResponse(
        answer=answer,
        sources=[sources] if sources else [],
        confidence=confidence,
        followup_questions=await generate_followup_questions(query, answer),
    )
```

---

### 3.7 Файлы для создания (Этап 3)

```
app/integrations/telegram/
├── __init__.py
├── bot_handler.py           # TelegramBotHandler класс
├── session_manager.py       # SessionManager класс
├── dialog_manager.py        # DialogManager класс
├── context_store.py         # ContextStore класс
├── models.py                # Pydantic модели (UserSession и т.д.)
├── commands/
│   ├── __init__.py
│   ├── start.py
│   ├── ask.py
│   ├── clear.py
│   ├── history.py
│   ├── rate.py
│   └── settings.py
└── main.py                  # Точка входа для запуска бота

scripts/
└── run_telegram_bot.py      # Скрипт для запуска бота
```

---

### 3.8 Конфигурация Telegram бота

**`app/config/telegram_config.py`:**

```python
from pydantic import BaseModel

class TelegramConfig(BaseModel):
    token: str  # из .env: TELEGRAM_BOT_TOKEN
    webhook_url: Optional[str] = None  # для продакшена
    max_conversation_length: int = 50  # максимум сообщений в истории
    session_ttl_hours: int = 24  # время жизни сессии
    enable_analytics: bool = True
    allowed_user_ids: Optional[List[int]] = None  # если нужно ограничить доступ

class TelegramIntegrationSettings(BaseModel):
    enabled: bool = True
    config: TelegramConfig
```

**`.env` пример:**

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook
```

---

## 🎯 ЭТАП 4: Диалоговая логика и улучшения — 2-3 дня

### 4.1 Follow-up вопросы

**Логика генерации уточняющих вопросов:**

```python
async def generate_followup_questions(
    original_query: str,
    answer: str,
    context_docs: List[str]
) -> List[str]:
    """
    На основе ответа генерирует 3 уточняющих вопроса.
    """

    # Правила (без LLM):
    1. Если ответ упомянул related_topics в метаданных
       → добавить вопрос про related_topic

    2. Если ответ неполный (has_complete_answer = false)
       → добавить вопрос "Хотите узнать более подробно?"

    3. Если вопрос был про исключение
       → предложить противоположный вопрос
       Пример: "Как НЕ делать" → "Как делать правильно?"

    Результат: List[str] с 3 предложениями
```

---

### 4.2 Feedback система

**Логика сбора обратной связи:**

```python
class FeedbackStore:
    """
    Сбор рейтингов пользователей и отзывов.
    """

    async def save_rating(
        user_id: int,
        query: str,
        answer: str,
        rating: int,  # 1-5
        comment: Optional[str] = None
    ):
        """
        Сохранить рейтинг ответа.
        Используется для:
        - Улучшения пайплайна
        - Переобучения модели ранжирования
        - Анализа проблемных вопросов
        """
        pass

    async def get_feedback_analytics() -> FeedbackStats:
        """
        Получить статистику по рейтингам.
        """
        pass
```

---

### 4.3 Интеграция с Langfuse

**Отслеживание метрик в Telegram контексте:**

```python
@observe()  # Langfuse трейсинг
async def process_query(user_id: int, query: str) -> DialogResponse:
    """
    Все вызовы пайплайна логируются в Langfuse с:
    - user_id (для отслеживания поведения пользователя)
    - session_id (для анализа диалогов)
    - complexity_level (для анализа типов вопросов)
    - cache_hit (был ли использован кэш)
    - multihop_used (была ли использована multi-hop логика)
    - response_time
    - user_rating (если пользователь оценил)
    """
```

---

## 📊 Полная архитектура после всех этапов

```
┌─────────────────────────────────────────────────────────────┐
│                         Telegram User                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  /ask "вопрос"  →  SessionManager → DialogManager           │
│                                          ↓                   │
│                     ┌─────────────────────────────────────┐  │
│                     │      RAG Pipeline (Enhanced)        │  │
│                     ├─────────────────────────────────────┤  │
│                     │ 1. Check Cache                      │  │
│                     │    ├─ if hit → return cached        │  │
│                     │    └─ if miss → continue            │  │
│                     │                                      │  │
│                     │ 2. Classify (intent, category)      │  │
│                     │ 3. Metadata Filter                  │  │
│                     │ 4. Retrieve (top-k docs)            │  │
│                     │ 5. Complexity Detection             │  │
│                     │ 6. Multi-Hop Resolver (if complex)  │  │
│                     │    ├─ Hop 0: primary doc            │  │
│                     │    ├─ Hop 1+: related docs          │  │
│                     │    └─ Merge context                 │  │
│                     │ 7. Generate Answer                  │  │
│                     │ 8. Route (auto_reply/handoff)       │  │
│                     │ 9. Store in Cache                   │  │
│                     └─────────────────────────────────────┘  │
│                                    ↓                         │
│                     DialogResponse + metadata               │
│                                    ↓                         │
│              Format answer + show sources + rate            │
│                                                               │
└─────────────────────────────────────────────────────────────┘

Storage Layer:
├─ PostgreSQL (docs, embeddings, cache)
├─ Redis (session cache, query cache)
├─ Langfuse (monitoring, evaluation)
└─ Telegram API (message delivery)
```

---

## ⏱️ Таймлайн реализации

```
ЭТАП 1: Multi-Hop рассуждения — 5-6 дней
├─ 1.1 Complexity Detector — 1 день
├─ 1.2 Hop Resolver — 1.5 дней
├─ 1.3 Relation Graph — 0.5 дней
├─ 1.4 Context Merger — 0.5 дней
├─ 1.5 Интеграция + тесты — 1.5 дней

ЭТАП 2: Кеширование — 3-4 дня
├─ 2.1 Query Normalizer — 0.5 дней
├─ 2.2 Cache Layer — 1 день
├─ 2.3 Statistics + Monitoring — 0.5 дней
├─ 2.4 Интеграция + тесты — 1.5 дней

ЭТАП 3: Telegram интеграция — 4-5 дней
├─ 3.1 Session Manager — 1 день
├─ 3.2 Dialog Manager — 1 день
├─ 3.3 Bot Handler + Commands — 1.5 дней
├─ 3.4 Context Store — 0.5 дней
├─ 3.5 Интеграция + тесты — 1 день

ЭТАП 4: Диалоговая логика — 2-3 дня
├─ 4.1 Follow-up questions — 0.5 дней
├─ 4.2 Feedback система — 1 день
├─ 4.3 Langfuse интеграция — 0.5 дней
├─ 4.4 E2E тестирование — 1 день

────────────────────────────────────
ИТОГО: 14-18 дней (или 10-14 дней параллельная разработка)
```

---

## 🔄 Рекомендуемый порядок разработки

### Вариант A: Последовательно (безопаснее)
1. Завершить Этап 1 (Multi-Hop) → интегрировать
2. Завершить Этап 2 (Cache) → интегрировать
3. Завершить Этап 3 (Telegram) → интегрировать
4. Завершить Этап 4 (Dialog logic) → интегрировать

**Преимущество:** Каждый этап тестируется независимо

---

### Вариант B: Параллельно (быстрее, требует координации)
- **Team 1:** Разработать Этап 1 (Multi-Hop)
- **Team 2:** Разработать Этап 2 (Cache) параллельно
- **Team 3:** Начать Этап 3 (Telegram) как только State обновлён
- **Integ lead:** Координировать интеграцию

**Преимущество:** Завершение за 10-14 дней

---

## 📚 Стандарты разработки

### Структура каждого узла/компонента:

```
component/
├── __init__.py              # export публичные классы
├── models.py                # Pydantic модели (Input/Output)
├── service.py               # основная логика
├── node.py                  # LangGraph узел (если нужен)
├── tests/
│   ├── __init__.py
│   ├── test_unit.py        # unit тесты
│   └── test_integration.py # интеграционные тесты
└── README.md                # документация компонента
```

### Правила кодирования:
- ✅ Type hints везде
- ✅ Docstrings (Google style)
- ✅ Error handling с custom исключениями
- ✅ Логирование на всех критических точках
- ✅ Unitосты для core логики (>80% coverage)
- ✅ Интеграционные тесты для узлов

### Тестирование:

```bash
# Unit тесты
pytest app/nodes/multihop/tests/test_unit.py -v

# Интеграционные тесты
pytest app/nodes/multihop/tests/test_integration.py -v

# E2E тесты (всей системы с Telegram)
pytest tests/e2e/test_telegram_flow.py -v

# Покрытие
pytest --cov=app --cov-report=html
```

---

## ✅ Метрики успеха

### Успех Этапа 1 (Multi-Hop):
- ✅ Детектор сложности: >85% accuracy на валидации
- ✅ Multi-hop улучшает recall на 20-30%
- ✅ Время обработки сложных вопросов <3 сек
- ✅ Интеграция в пайплайн без регрессии

### Успех Этапа 2 (Cache):
- ✅ Hit rate >40% на production данных
- ✅ Ускорение на 80-90% для кэшированных вопросов
- ✅ Сбережение времени >100 часов в месяц
- ✅ Точность ответов остаётся неизменной

### Успех Этапа 3 (Telegram):
- ✅ Бот поднимается без ошибок
- ✅ Обработка 100 одновременных сессий
- ✅ /clear работает, очищая всю историю
- ✅ Сохранение сессии 24+ часа

### Успех Этапа 4 (Dialog Logic):
- ✅ Follow-up questions релевантны в 90% случаев
- ✅ Feedback собирается и логируется
- ✅ E2E тест: вопрос → ответ → оценка → логирование

---

## 🚀 Развёртывание

### Dev:
```bash
# Запуск пайплайна
uvicorn app.main:app --reload

# Запуск Telegram бота
python scripts/run_telegram_bot.py
```

### Production:
```bash
# Docker compose для всех сервисов
docker-compose -f docker-compose.yml up -d

# Redis для кэша
docker run -d -p 6379:6379 redis:latest

# PostgreSQL + pgvector
docker run -d \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  pgvector/pgvector:latest
```

---

## 📝 Зависимости (requirements.txt добавить)

```
# Multi-Hop
spacy>=3.5.0  # для NER и токенизации
networkx>=3.0  # для графов связей

# Cache
redis>=5.0.0  # для кэша

# Telegram
python-telegram-bot>=20.0  # для Telegram бота
aiogram>=3.0.0  # альтернатива (более async-friendly)

# Feedback
sqlalchemy>=2.0  # для ORM (если используем PostgreSQL напрямую)

# Общее
pydantic>=2.0
langchain>=0.1.0
langgraph>=0.1.0
langfuse>=2.0.0
```

---

## 🎯 Следующие шаги

1. ✅ **Утвердить этот roadmap** с командой
2. 📝 **Создать issue/tasks** для каждого этапа
3. 🌿 **Создать feature branch:** `claude/multi-hop-telegram`
4. 🚀 **Начать разработку** с Этапа 1 (Multi-Hop)
5. 📊 **Отслеживать прогресс** через pull requests

---

**Happy coding! 🎉**
