from typing import Optional, Dict, Any
from app.settings import settings
from app.logging_config import logger

import httpx

class ChannelService:
    """Service for interacting with messaging channels (only Telegram supported)."""
    def __init__(self):
        """Initialize ChannelService with Telegram settings."""
        self.telegram_token = settings.TELEGRAM_TOKEN
        self.telegram_api_url = f"https://api.telegram.org/bot{self.telegram_token}"

    async def send_message(self, channel: str, user_id: str, text: str) -> Dict[str, Any]:
        """
        Send a message to a user on a specific channel.

        Args:
            channel: Channel name (e.g., 'telegram')
            user_id: User identifier for the channel (chat_id)
            text: Message content

        Returns:
            Dict containing API response

        Raises:
            ValueError: If channel is unsupported or token is missing
            Exception: If API request fails
        """
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
                logger.error("Failed to send telegram message", extra={"error": str(e), "user_id": user_id})
                raise Exception(f"Telegram API error: {str(e)}")

    async def edit_message(self, channel: str, user_id: str, message_id: str, text: str) -> Dict[str, Any]:
        """
        Edit an existing message.

        Args:
            channel: Channel name
            user_id: User identifier
            message_id: ID of the message to edit
            text: New message content

        Returns:
            Dict containing API response
        """
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
                logger.error("Failed to edit telegram message", extra={"error": str(e), "user_id": user_id, "message_id": message_id})
                raise Exception(f"Telegram API error: {str(e)}")

    async def delete_message(self, channel: str, user_id: str, message_id: str) -> Dict[str, Any]:
        """
        Delete a message.

        Args:
            channel: Channel name
            user_id: User identifier
            message_id: ID of the message to delete

        Returns:
            Dict containing API response
        """
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
                logger.error("Failed to delete telegram message", extra={"error": str(e), "user_id": user_id, "message_id": message_id})
                raise Exception(f"Telegram API error: {str(e)}")

channel_service = ChannelService()
