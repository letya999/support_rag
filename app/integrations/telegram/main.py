"""
Telegram Bot Entry Point

Main entry point for running the Telegram bot service.
Runs as: python -m app.integrations.telegram.main
"""

import asyncio
import logging
import os
import sys

from app.integrations.telegram.bot import SupportRAGBot
from app.integrations.telegram.storage import SessionStorage
from app.integrations.telegram.pipeline_client import RAGPipelineClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('telegram_bot.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Initialize and start the Telegram bot"""

    # Get environment variables
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    api_url = os.getenv("API_URL", "http://localhost:8000")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Validate required variables
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set in environment")
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")

    logger.info(f"Initializing bot with API URL: {api_url}")
    logger.info(f"Redis URL: {redis_url}")

    # Initialize components
    storage = SessionStorage(redis_url)
    rag_client = RAGPipelineClient(api_url)

    # Connect to external services
    try:
        await storage.connect()
        await rag_client.connect()
        logger.info("Connected to storage and RAG pipeline")
    except Exception as e:
        logger.error(f"Failed to connect to services: {e}")
        raise

    # Create and start bot
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
        logger.info("Cleaning up...")
        await bot.stop()
        await rag_client.disconnect()
        await storage.disconnect()
        logger.info("Cleanup complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
