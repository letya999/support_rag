from typing import Optional, Tuple, Any
from redis import asyncio as aioredis
from redis.asyncio import Redis

class RedisConnector:
    """
    Manages Redis connection and basic operations.
    """
    def __init__(self, url: str):
        self.url = url
        self.client: Optional[Redis] = None

    async def connect(self) -> bool:
        """Establish connection to Redis."""
        try:
            # decode_responses=False because we store JSON bytes or let Pydantic handle it?
            # Original code used decode_responses=False
            self.client = await aioredis.from_url(self.url, decode_responses=False)
            await self.client.ping()
            print("✅ Redis connected successfully")
            return True
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}. Using in-memory cache.")
            self.client = None
            return False

    async def close(self):
        """Close connection."""
        if self.client:
            await self.client.close()
            self.client = None

    def is_available(self) -> bool:
        """Check if Redis client is connected."""
        return self.client is not None

    async def ping(self):
        if self.client:
            return await self.client.ping()

    async def info(self, section: str = "default") -> dict:
        """Get Redis server info."""
        if self.client:
            return await self.client.info(section)
        return {}


    async def setex(self, key: str, time: int, value: Any):
        if self.client:
            await self.client.setex(key, time, value)

    async def get(self, key: str) -> Any:
        if self.client:
            return await self.client.get(key)
        return None

    async def delete(self, *keys: str) -> int:
        if self.client and keys:
            return await self.client.delete(*keys)
        return 0

    async def scan(self, cursor: int, match: str) -> Tuple[int, list]:
        if self.client:
            return await self.client.scan(cursor, match=match)
        return 0, []
