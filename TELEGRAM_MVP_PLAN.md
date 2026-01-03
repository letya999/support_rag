# 🤖 Telegram Bot MVP - Полный План

## 1. Архитектура

### 1.1 Docker Структура

```
docker-compose.yml
├── api (FastAPI) - основной RAG пайплайн
├── telegram-bot (python-telegram-bot) - бот сервис
├── postgres - БД с pgvector
├── redis - кеш сессий
└── qdrant - vector store (если используется)
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: support_rag
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    environment:
      DATABASE_URL: postgresql://postgres:${DB_PASSWORD}@postgres:5432/support_rag
      REDIS_URL: redis://redis:6379
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
      - qdrant
    command: uvicorn app.main:app --host 0.0.0.0 --reload

  telegram-bot:
    build:
      context: .
      dockerfile: Dockerfile.bot
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      API_URL: http://api:8000
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://postgres:${DB_PASSWORD}@postgres:5432/support_rag
    depends_on:
      - api
      - redis
      - postgres
    command: python -m app.integrations.telegram.main
    restart: always

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

---

## 2. Структура Файлов

```
app/integrations/telegram/
├── __init__.py
├── main.py                  # Точка входа бота (вместо скрипта)
├── bot.py                   # TelegramBotHandler класс
├── models.py                # UserSession, Message
├── storage.py               # SessionStorage (Redis)
└── pipeline_client.py       # Клиент для API пайплайна

Dockerfile.bot              # Docker для бота
Dockerfile.api              # Docker для API (если нужно)
docker-compose.yml
```

---

## 3. Модели Данных (models.py)

```python
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

class Message(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime
    # Для логирования и аналитики
    query_id: Optional[str] = None  # ID запроса в RAG пайплайне

class UserSession(BaseModel):
    user_id: int
    username: str
    messages: List[Message] = []
    created_at: datetime
    last_activity: datetime
    is_active: bool = True

class RAGRequest(BaseModel):
    """Запрос к RAG пайплайну"""
    question: str
    conversation_history: List[dict]  # [{"role": "user", "content": "..."}, ...]
    user_id: str
    session_id: str

class RAGResponse(BaseModel):
    """Ответ от RAG пайплайна"""
    answer: str
    sources: List[dict]  # [{"title": str, "doc_id": str, "relevance": float}, ...]
    confidence: float
    query_id: str
    metadata: Optional[dict] = None
```

---

## 4. Хранилище Сессий (storage.py)

**Redis хранит сессии пользователей**

```python
import json
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import Optional

class SessionStorage:
    """
    Хранилище сессий в Redis.
    Ключ: user:{user_id}
    TTL: 24 часа (если захотим расширить позже)
    """

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: Optional[redis.Redis] = None
        self.SESSION_TTL = 24 * 60 * 60  # 24 часа

    async def connect(self):
        self.redis = await redis.from_url(self.redis_url)

    async def disconnect(self):
        await self.redis.close()

    async def get_session(self, user_id: int) -> Optional[UserSession]:
        """Получить сессию пользователя"""
        data = await self.redis.get(f"user:{user_id}")
        if not data:
            return None

        session_dict = json.loads(data)
        # Десериализовать Message объекты
        messages = [
            Message(
                role=msg["role"],
                content=msg["content"],
                timestamp=datetime.fromisoformat(msg["timestamp"]),
                query_id=msg.get("query_id")
            )
            for msg in session_dict.get("messages", [])
        ]

        session_dict["messages"] = messages
        session_dict["created_at"] = datetime.fromisoformat(session_dict["created_at"])
        session_dict["last_activity"] = datetime.fromisoformat(session_dict["last_activity"])

        return UserSession(**session_dict)

    async def save_session(self, session: UserSession):
        """Сохранить сессию"""
        session_dict = {
            "user_id": session.user_id,
            "username": session.username,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "query_id": msg.query_id
                }
                for msg in session.messages
            ],
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "is_active": session.is_active
        }

        await self.redis.setex(
            f"user:{session.user_id}",
            self.SESSION_TTL,
            json.dumps(session_dict)
        )

    async def add_message(
        self,
        user_id: int,
        role: MessageRole,
        content: str,
        query_id: Optional[str] = None
    ):
        """Добавить сообщение к сессии"""
        session = await self.get_session(user_id)
        if not session:
            raise ValueError(f"Session not found for user {user_id}")

        message = Message(
            role=role,
            content=content,
            timestamp=datetime.now(),
            query_id=query_id
        )
        session.messages.append(message)
        session.last_activity = datetime.now()

        await self.save_session(session)

    async def clear_session(self, user_id: int):
        """Очистить историю сессии (но сама сессия остаётся)"""
        session = await self.get_session(user_id)
        if session:
            session.messages = []
            session.last_activity = datetime.now()
            await self.save_session(session)

    async def delete_session(self, user_id: int):
        """Полностью удалить сессию"""
        await self.redis.delete(f"user:{user_id}")

    async def get_session_context(
        self,
        user_id: int,
        max_messages: int = 6
    ) -> List[dict]:
        """
        Получить последние N сообщений для контекста в RAG.
        Вернуть в формате: [{"role": "user", "content": "..."}, ...]
        """
        session = await self.get_session(user_id)
        if not session:
            return []

        # Последние max_messages сообщений (исключая самое новое)
        messages = session.messages[-(max_messages):]

        return [
            {
                "role": msg.role.value,  # "user" или "assistant"
                "content": msg.content
            }
            for msg in messages
        ]
```

---

## 5. Клиент RAG Пайплайна (pipeline_client.py)

**Коммуникация с основным API через HTTP**

```python
import aiohttp
import logging
from typing import List, Optional
from app.integrations.telegram.models import RAGRequest, RAGResponse

logger = logging.getLogger(__name__)

class RAGPipelineClient:
    """
    Клиент для взаимодействия с RAG пайплайном через API.
    Основной API запускается в отдельном контейнере.
    """

    def __init__(self, api_url: str):
        """
        api_url: "http://api:8000" (внутри Docker сети)
        """
        self.api_url = api_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None

    async def connect(self):
        """Инициализировать HTTP сессию"""
        self.session = aiohttp.ClientSession()

    async def disconnect(self):
        """Закрыть HTTP сессию"""
        if self.session:
            await self.session.close()

    async def query_rag(
        self,
        question: str,
        conversation_history: List[dict],
        user_id: int,
        session_id: str
    ) -> RAGResponse:
        """
        Запрос к RAG пайплайну.

        Args:
            question: Вопрос пользователя
            conversation_history: История диалога для контекста
            user_id: ID пользователя в Telegram
            session_id: ID сессии

        Returns:
            RAGResponse с ответом и метаданными
        """

        request = RAGRequest(
            question=question,
            conversation_history=conversation_history,
            user_id=str(user_id),
            session_id=session_id
        )

        try:
            async with self.session.post(
                f"{self.api_url}/api/rag/query",
                json=request.dict(),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    logger.error(
                        f"RAG API error: {response.status} - {await response.text()}"
                    )
                    # Fallback ответ при ошибке
                    return RAGResponse(
                        answer="Извините, не смог обработать ваш вопрос. Попробуйте позже.",
                        sources=[],
                        confidence=0.0,
                        query_id="error"
                    )

                data = await response.json()
                return RAGResponse(**data)

        except aiohttp.ClientError as e:
            logger.error(f"RAG API connection error: {e}")
            return RAGResponse(
                answer="Ошибка подключения к сервису. Попробуйте позже.",
                sources=[],
                confidence=0.0,
                query_id="connection_error"
            )
```

---

## 6. Telegram Bot Handler (bot.py)

**Основная логика бота**

```python
import logging
from datetime import datetime
from typing import Optional
from telegram import Update, ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from app.integrations.telegram.models import UserSession, MessageRole
from app.integrations.telegram.storage import SessionStorage
from app.integrations.telegram.pipeline_client import RAGPipelineClient

logger = logging.getLogger(__name__)

class SupportRAGBot:
    """Telegram бот для поддержки с RAG пайплайном"""

    def __init__(
        self,
        token: str,
        storage: SessionStorage,
        rag_client: RAGPipelineClient
    ):
        self.token = token
        self.storage = storage
        self.rag_client = rag_client

        self.app = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        """Регистрация обработчиков команд и сообщений"""

        # Команды
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("history", self.cmd_history))

        # Все остальные текстовые сообщения
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /start - инициализировать сессию пользователя
        """
        user_id = update.effective_user.id
        username = update.effective_user.username or "User"

        # Проверить, есть ли уже сессия
        existing_session = await self.storage.get_session(user_id)

        if not existing_session:
            # Создать новую сессию
            session = UserSession(
                user_id=user_id,
                username=username,
                messages=[],
                created_at=datetime.now(),
                last_activity=datetime.now(),
                is_active=True
            )
            await self.storage.save_session(session)
            logger.info(f"Created new session for user {user_id} (@{username})")
        else:
            logger.info(f"User {user_id} already has active session")

        await update.message.reply_text(
            f"👋 Привет, {username}!\n\n"
            "Я Support RAG бот. Просто пиши свои вопросы, "
            "и я отвечу на основе документов.\n\n"
            "Для справки введи /help"
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /help - справка по использованию
        """
        await update.message.reply_text(
            "📖 **Как я работаю:**\n\n"
            "1️⃣ Просто пиши вопрос (без команд)\n"
            "2️⃣ Я ищу ответ в документах\n"
            "3️⃣ Если не знаю - скажу честно\n\n"
            "**Команды:**\n"
            "/start - начать новую сессию\n"
            "/history - показать историю диалога\n"
            "/help - эта справка\n\n"
            "**Для новой сессии:** просто удали бота из чата и добавь снова",
            parse_mode="Markdown"
        )

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /history - показать последние сообщения
        """
        user_id = update.effective_user.id
        session = await self.storage.get_session(user_id)

        if not session or len(session.messages) == 0:
            await update.message.reply_text("📝 История диалога пуста.")
            return

        # Последние 10 сообщений
        messages = session.messages[-10:]
        text = "📝 **История диалога (последние 10):**\n\n"

        for msg in messages:
            role_emoji = "👤" if msg.role == MessageRole.USER else "🤖"
            # Обрезать длинные сообщения
            content = msg.content[:150]
            if len(msg.content) > 150:
                content += "..."
            text += f"{role_emoji} {content}\n\n"

        await update.message.reply_text(text, parse_mode="Markdown")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Основной обработчик сообщений пользователя.

        Flow:
        1. Получить/создать сессию
        2. Добавить сообщение пользователя в историю
        3. Получить контекст диалога (последние N сообщений)
        4. Отправить запрос в RAG пайплайн через API
        5. Получить ответ
        6. Добавить ответ в историю
        7. Отправить ответ пользователю
        """
        user_id = update.effective_user.id
        query = update.message.text

        logger.info(f"User {user_id}: {query[:50]}...")

        try:
            # 1. Показать "печатает..."
            await update.message.chat.send_action(ChatAction.TYPING)

            # 2. Получить/создать сессию
            session = await self.storage.get_session(user_id)

            if not session:
                # Создать новую, если не существует
                username = update.effective_user.username or "User"
                session = UserSession(
                    user_id=user_id,
                    username=username,
                    messages=[],
                    created_at=datetime.now(),
                    last_activity=datetime.now(),
                    is_active=True
                )
                await self.storage.save_session(session)
                logger.info(f"Auto-created session for user {user_id}")

            # 3. Добавить вопрос пользователя в историю
            await self.storage.add_message(
                user_id=user_id,
                role=MessageRole.USER,
                content=query
            )

            # 4. Получить контекст диалога (последние 6 сообщений = 3 диалога)
            conversation_context = await self.storage.get_session_context(
                user_id=user_id,
                max_messages=6
            )

            # 5. Запрос к RAG пайплайну
            logger.info(f"Querying RAG pipeline for user {user_id}")

            rag_response = await self.rag_client.query_rag(
                question=query,
                conversation_history=conversation_context,
                user_id=user_id,
                session_id=f"{user_id}_{session.created_at.timestamp()}"
            )

            # 6. Добавить ответ в историю
            await self.storage.add_message(
                user_id=user_id,
                role=MessageRole.ASSISTANT,
                content=rag_response.answer,
                query_id=rag_response.query_id
            )

            # 7. Форматировать и отправить ответ
            response_text = f"🤖 {rag_response.answer}"

            # Добавить источники, если есть
            if rag_response.sources:
                response_text += "\n\n📚 **Источники:**"
                for src in rag_response.sources[:3]:
                    title = src.get("title", "Документ")
                    relevance = src.get("relevance", 0)
                    response_text += f"\n- {title}"
                    if relevance > 0:
                        response_text += f" ({relevance:.0%})"

            # Добавить информацию о доверии
            if rag_response.confidence > 0:
                response_text += f"\n\n🎯 Уверенность: {rag_response.confidence:.0%}"

            await update.message.reply_text(response_text, parse_mode="Markdown")

            logger.info(f"Response sent to user {user_id}")

        except Exception as e:
            logger.error(f"Error processing message from {user_id}: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке вопроса. Попробуйте позже."
            )

    async def start(self):
        """Запустить бота"""
        logger.info("Starting Telegram bot...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(
            allowed_updates=["message", "callback_query"]
        )
        logger.info("Bot is polling...")

    async def stop(self):
        """Остановить бота"""
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        logger.info("Bot stopped")
```

---

## 7. Точка входа (main.py)

**Запускается как модуль Python в Docker**

```python
import asyncio
import logging
import os
from app.integrations.telegram.bot import SupportRAGBot
from app.integrations.telegram.storage import SessionStorage
from app.integrations.telegram.pipeline_client import RAGPipelineClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Инициализировать и запустить бота"""

    # Получить переменные окружения
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    api_url = os.getenv("API_URL", "http://localhost:8000")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не установлен в .env")

    logger.info(f"Initializing bot with API URL: {api_url}")

    # Инициализировать компоненты
    storage = SessionStorage(redis_url)
    rag_client = RAGPipelineClient(api_url)

    # Подключиться к внешним сервисам
    await storage.connect()
    await rag_client.connect()

    logger.info("Connected to storage and RAG pipeline")

    # Создать и запустить бота
    bot = SupportRAGBot(
        token=token,
        storage=storage,
        rag_client=rag_client
    )

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    finally:
        await bot.stop()
        await rag_client.disconnect()
        await storage.disconnect()
        logger.info("Cleanup complete")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. Dockerfile для бота (Dockerfile.bot)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установить зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копировать код приложения
COPY . .

# Запустить бота как модуль
CMD ["python", "-m", "app.integrations.telegram.main"]
```

---

## 9. Интеграция RAG пайплайна

**В app/pipeline/graph.py или app/main.py (FastAPI):**

```python
# В основном API должен быть endpoint для обработки запросов от бота

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI()

@app.post("/api/rag/query")
async def rag_query(request: dict):
    """
    Endpoint для обработки запроса от Telegram бота.

    Request:
    {
        "question": "...",
        "conversation_history": [{"role": "user", "content": "..."}, ...],
        "user_id": "123456",
        "session_id": "123456_1234567890"
    }

    Response:
    {
        "answer": "...",
        "sources": [{"title": "...", "doc_id": "...", "relevance": 0.95}, ...],
        "confidence": 0.85,
        "query_id": "query_123",
        "metadata": {...}
    }
    """

    question = request.get("question")
    conversation_history = request.get("conversation_history", [])
    user_id = request.get("user_id")
    session_id = request.get("session_id")

    try:
        # Запустить RAG граф с контекстом диалога
        input_state = {
            "question": question,
            "conversation_context": conversation_history,
            "user_id": user_id,
            "session_id": session_id
        }

        # Выполнить граф (синхронно или асинхронно в зависимости от реализации)
        result = await rag_graph.ainvoke(input_state)

        # Форматировать результат
        return {
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "confidence": result.get("confidence", 0.0),
            "query_id": result.get("query_id", ""),
            "metadata": result.get("metadata", {})
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 10. .env файл

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_token_here

# API
API_URL=http://api:8000

# Database
DATABASE_URL=postgresql://postgres:password@postgres:5432/support_rag

# Redis
REDIS_URL=redis://redis:6379

# OpenAI
OPENAI_API_KEY=sk-...
```

---

## 11. Требования requirements.txt

```
python-telegram-bot>=21.0
aiohttp>=3.9.0
redis>=5.0.0
pydantic>=2.0.0
asyncio
```

---

## 12. Flow обработки сообщения

```
User пишет сообщение в Telegram
    ↓
handle_message() получает сообщение
    ↓
Получить/создать UserSession из Redis
    ↓
Добавить вопрос в conversation_history
    ↓
Получить последние N сообщений (контекст диалога)
    ↓
HTTP POST на /api/rag/query с вопросом + контекстом
    ↓
RAG пайплайн обрабатывает с контекстом:
  - Определяет релевантность к предыдущим вопросам
  - Ищет документы в vector store
  - Генерирует ответ с учётом контекста
    ↓
Получить RAGResponse (answer, sources, confidence)
    ↓
Добавить ответ в conversation_history
    ↓
Отправить ответ пользователю в Telegram
```

---

## 13. Запуск

```bash
# В корне проекта
docker-compose up

# Или отдельно
docker-compose up api
docker-compose up telegram-bot
docker-compose up postgres redis qdrant
```

---

## 14. Особенности MVP

✅ **Простая архитектура** - бот и API в отдельных контейнерах
✅ **Полная интеграция** - контекст диалога передаётся в RAG пайплайн
✅ **Минимум команд** - /start, /help, /history
✅ **История диалога** - хранится в Redis, используется для контекста
✅ **Тестирование** - легко тестировать логику диалога через бота
✅ **Масштабируемость** - бот и API независимы, можно запустить несколько ботов

---

## 15. Дальнейшие расширения (после MVP)

- [ ] Оценки ответов (/rate)
- [ ] Уточняющие вопросы
- [ ] Настройки языка
- [ ] Аналитика (Langfuse интеграция)
- [ ] Кешировать частые вопросы
