"""
Telegram Bot Handler

Main bot logic for handling user messages and responses.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from app.integrations.telegram.models import MessageRole
from app.integrations.telegram.pipeline_client import RAGPipelineClient

logger = logging.getLogger(__name__)


class SupportRAGBot:
    """
    Telegram bot for support with RAG pipeline integration.

    Handles user messages, passes them through RAG pipeline.
    Stateless architecture: relies on API for conversation history.
    """

    def __init__(
        self,
        token: str,
        rag_client: RAGPipelineClient
    ):
        """
        Initialize the bot.

        Args:
            token: Telegram bot token
            rag_client: RAGPipelineClient instance for querying the RAG pipeline
        """
        self.token = token
        self.rag_client = rag_client

        self.app = Application.builder().token(token).build()
        
        # Phrases will be loaded from API on startup
        self.phrases_config: Dict[str, Any] = {}
        
        self._setup_handlers()
    
    async def load_phrases_from_api(self):
        """
        Load bot phrases configuration from API endpoint.
        
        This eliminates the need for direct file access to API container's YAML configs.
        """
        try:
            async with self.rag_client.session.get(
                f"{self.rag_client.api_url}/api/v1/config/bot-phrases"
            ) as response:
                if response.status == 200:
                    payload = await response.json()
                    self.phrases_config = payload.get("data", {})
                    logger.info(f"Loaded {len(self.phrases_config)} phrase keys from API")
                else:
                    logger.error(f"Failed to load phrases from API: {response.status}")
                    self.phrases_config = {}
        except Exception as e:
            logger.error(f"Error loading phrases from API: {e}")
            self.phrases_config = {}

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
        # self.app.add_handler(CommandHandler("history", self.cmd_history)) # History requires API endpoint

        # All other text messages
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /start command - initialize interaction.
        """
        user = update.effective_user
        username = user.username or "User"

        try:
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

            # 2. Derive Session ID
            # We use a persistent session ID based on user_id to maintain history on backend
            # A timestamp component would break history if the bot restarts, so we use a constant suffix or just user_id
            # However, usually we want sessions to expire. 
            # For simplicity and robustness with the described architecture, let's use user_id as part of session.
            # But the backend separates user_id and session_id.
            # Let's map Telegram User ID -> Backend User ID. 
            # Session ID can be "telegram_session_{user_id}" to keep it simple and persistent for the user.
            session_id = f"tg_sess_{user_id}"

            # 3. Query RAG pipeline
            # Note: We send EMPTY conversation_history because we trust the backend to load it via SessionStarterNode
            logger.info(f"Querying RAG pipeline for user {user_id} (session {session_id})")
            
            user_metadata = {
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "language_code": user.language_code,
                "is_bot": user.is_bot,
                "source": "telegram"
            }

            rag_response = await self.rag_client.query_rag(
                question=query,
                conversation_history=[], # Backend loads history!
                user_id=str(user_id),
                session_id=session_id,
                user_metadata=user_metadata
            )

            # 4. Format and send response
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
