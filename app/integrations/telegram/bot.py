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
from app.services.config_loader.loader import load_shared_config

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
        
        # Load phrases config
        self.phrases_config = load_shared_config("system_phrases").get("telegram_bot_phrases", {})
        
        self._setup_handlers()

    def _get_phrase(self, key: str, **kwargs) -> str:
        """Helper to get bilingual phrase from config formatted with kwargs"""
        phrase_data = self.phrases_config.get(key, {})
        if not phrase_data:
            return f"[{key}]"
        
        text_en = phrase_data.get("en", "").format(**kwargs)
        text_ru = phrase_data.get("ru", "").format(**kwargs)
        
        return f"{text_en}\n\n{text_ru}"

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
                self._get_phrase("start_greeting", username=username)
            )
        except Exception as e:
            logger.error(f"Error in /start command: {e}")
            await update.message.reply_text(
                self._get_phrase("error_init")
            )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /help command - show help information.
        """
        try:
            await update.message.reply_text(
                self._get_phrase("help_text"),
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
                await update.message.reply_text(self._get_phrase("history_empty"))
                return

            # Last 10 messages
            messages = session.messages[-10:]
            text = self._get_phrase("history_header") + "\n\n"

            for msg in messages:
                role_msg = "User" if msg.role == MessageRole.USER else "Bot"
                # Truncate long messages
                content = msg.content[:150]
                if len(msg.content) > 150:
                    content += "..."
                text += f"**{role_msg}:** {content}\n\n"

            await update.message.reply_text(text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in /history command: {e}")
            await update.message.reply_text(
                self._get_phrase("error_history")
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

            # 7. Format and send response (Just the answer, no emojis/sources)
            await update.message.reply_text(rag_response.answer, parse_mode="Markdown")

            logger.info(f"Response sent to user {user_id}")

        except Exception as e:
            logger.error(f"Error processing message from {user_id}: {e}", exc_info=True)
            await update.message.reply_text(
                self._get_phrase("error_processing")
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
