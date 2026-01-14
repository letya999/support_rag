from redis import asyncio as aioredis
from typing import Optional
from app.settings import settings

class RedisPool:
    _instance = None
    _pool = None

    @classmethod
    async def get_pool(cls) -> aioredis.Redis:
        if cls._pool is None:
            # redis.from_url returns a Redis client which handles a connection pool internally
            cls._pool = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10
            )
        return cls._pool

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
