"""
Telegram Bot Handler

Main bot logic for handling user messages and responses.
"""

import logging
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from app.integrations.telegram.models import UserSession, MessageRole
from app.integrations.telegram.storage import SessionStorage
from app.integrations.telegram.pipeline_client import RAGPipelineClient

logger = logging.getLogger(__name__)


class SupportRAGBot:
    """
    Telegram bot for support with RAG pipeline integration.

    Handles user messages, passes them through RAG pipeline with conversation context,
    and stores conversation history.
    """

    def __init__(
        self,
        token: str,
        storage: SessionStorage,
        rag_client: RAGPipelineClient
    ):
        """
        Initialize the bot.

        Args:
            token: Telegram bot token
            storage: SessionStorage instance for managing user sessions
            rag_client: RAGPipelineClient instance for querying the RAG pipeline
        """
        self.token = token
        self.storage = storage
        self.rag_client = rag_client

        self.app = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        """Register command and message handlers"""

        # Commands
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("history", self.cmd_history))

        # All other text messages
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /start command - initialize user session.

        If session doesn't exist, create a new one.
        """
        user_id = update.effective_user.id
        username = update.effective_user.username or "User"

        try:
            # Check if session already exists
            existing_session = await self.storage.get_session(user_id)

            if not existing_session:
                # Create new session
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
        except Exception as e:
            logger.error(f"Error in /start command: {e}")
            await update.message.reply_text(
                "❌ Ошибка при инициализации. Попробуйте позже."
            )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /help command - show help information.
        """
        try:
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
        except Exception as e:
            logger.error(f"Error in /help command: {e}")

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /history command - show recent conversation messages.
        """
        user_id = update.effective_user.id

        try:
            session = await self.storage.get_session(user_id)

            if not session or len(session.messages) == 0:
                await update.message.reply_text("📝 История диалога пуста.")
                return

            # Last 10 messages
            messages = session.messages[-10:]
            text = "📝 **История диалога (последние 10):**\n\n"

            for msg in messages:
                role_emoji = "👤" if msg.role == MessageRole.USER else "🤖"
                # Truncate long messages
                content = msg.content[:150]
                if len(msg.content) > 150:
                    content += "..."
                text += f"{role_emoji} {content}\n\n"

            await update.message.reply_text(text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in /history command: {e}")
            await update.message.reply_text(
                "❌ Ошибка при получении истории. Попробуйте позже."
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Main message handler.
        """
        user = update.effective_user
        user_id = user.id
        query = update.message.text

        logger.info(f"User {user_id}: {query[:50]}...")

        try:
            # 1. Show typing indicator
            await update.message.chat.send_action(ChatAction.TYPING)

            # 2. Get/create user session
            session = await self.storage.get_session(user_id)

            if not session:
                # Auto-create session if doesn't exist
                username = user.username or "User"
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

            # 3. Add user message to history
            await self.storage.add_message(
                user_id=user_id,
                role=MessageRole.USER,
                content=query
            )

            # 4. Get conversation context for RAG
            conversation_context = await self.storage.get_session_context(
                user_id=user_id,
                max_messages=6  # Last 3 dialogue turns
            )

            # 5. Query RAG pipeline
            logger.info(f"Querying RAG pipeline for user {user_id}")
            
            # Extract User Metadata
            user_metadata = {
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "language_code": user.language_code,
                "is_premium": getattr(user, "is_premium", False),
                "is_bot": user.is_bot
            }

            rag_response = await self.rag_client.query_rag(
                question=query,
                conversation_history=conversation_context,
                user_id=user_id,
                session_id=f"{user_id}_{session.created_at.timestamp()}",
                user_metadata=user_metadata
            )

            # 6. Add assistant response to history
            await self.storage.add_message(
                user_id=user_id,
                role=MessageRole.ASSISTANT,
                content=rag_response.answer,
                query_id=rag_response.query_id
            )

            # 7. Format and send response
            response_text = f"🤖 {rag_response.answer}"

            # Add sources if available
            if rag_response.sources:
                response_text += "\n\n📚 **Источники:**"
                for src in rag_response.sources[:3]:
                    title = src.get("title", "Документ")
                    relevance = src.get("relevance", 0)
                    response_text += f"\n- {title}"
                    if relevance > 0:
                        response_text += f" ({relevance:.0%})"

            # Add confidence score if available
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
        """Start the bot polling"""
        logger.info("Starting Telegram bot...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(
            allowed_updates=["message", "callback_query"]
        )
        logger.info("Bot is polling...")

    async def stop(self):
        """Stop the bot"""
        logger.info("Stopping bot...")
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        logger.info("Bot stopped")
