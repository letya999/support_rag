import httpx
import logging
from typing import Optional, Dict, Any
from app.settings import settings

logger = logging.getLogger(__name__)

class ChannelService:
    def __init__(self):
        self.telegram_token = settings.TELEGRAM_TOKEN
        self.telegram_api_url = f"https://api.telegram.org/bot{self.telegram_token}"

    async def send_message(self, channel: str, user_id: str, text: str) -> Dict[str, Any]:
        if channel.lower() != "telegram":
            raise ValueError(f"Unsupported channel: {channel}")
        
        if not self.telegram_token:
            raise ValueError("Telegram token not configured")

        async with httpx.AsyncClient() as client:
            url = f"{self.telegram_api_url}/sendMessage"
            payload = {
                "chat_id": user_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            try:
                response = await client.post(url, json=payload, timeout=10.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to send telegram message: {e}")
                raise Exception(f"Telegram API error: {str(e)}")

    async def edit_message(self, channel: str, user_id: str, message_id: str, text: str) -> Dict[str, Any]:
        if channel.lower() != "telegram":
            raise ValueError(f"Unsupported channel: {channel}")
            
        if not self.telegram_token:
            raise ValueError("Telegram token not configured")

        async with httpx.AsyncClient() as client:
            url = f"{self.telegram_api_url}/editMessageText"
            payload = {
                "chat_id": user_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            try:
                response = await client.post(url, json=payload, timeout=10.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to edit telegram message: {e}")
                raise Exception(f"Telegram API error: {str(e)}")

    async def delete_message(self, channel: str, user_id: str, message_id: str) -> Dict[str, Any]:
        if channel.lower() != "telegram":
            raise ValueError(f"Unsupported channel: {channel}")
            
        if not self.telegram_token:
            raise ValueError("Telegram token not configured")

        async with httpx.AsyncClient() as client:
            url = f"{self.telegram_api_url}/deleteMessage"
            payload = {
                "chat_id": user_id,
                "message_id": message_id
            }
            try:
                response = await client.post(url, json=payload, timeout=10.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to delete telegram message: {e}")
                raise Exception(f"Telegram API error: {str(e)}")

channel_service = ChannelService()
