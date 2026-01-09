"""
Integration with translation services.
Wraps the singleton QueryTranslator for async usage.
"""
import asyncio
import logging
from app.services.translation.translator import translator

logger = logging.getLogger(__name__)

async def translate_text(text: str, target_lang: str = "en") -> str:
    """
    Translate text to target language using the configured translator.
    Runs the blocking translation in a thread pool.
    
    Args:
        text (str): Text to translate
        target_lang (str): Target language code (default "en")
        
    Returns:
        str: Translated text
    """
    if not text:
        return ""
        
    try:
        # Offload CPU-intensive translation to thread
        return await asyncio.to_thread(translator.translate_query, text, target_lang=target_lang)
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        # Fallback to original text
        return text
