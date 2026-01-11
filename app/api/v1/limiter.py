from fastapi_limiter import FastAPILimiter
from redis import asyncio as aioredis
from app.settings import settings
import logging

logger = logging.getLogger(__name__)

async def init_limiter():
    try:
        redis = await aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(redis)
        logger.info(f"Rate limiter initialized with Redis at {settings.REDIS_URL}")
    except Exception as e:
        logger.error(f"Failed to initialize rate limiter: {e}")
        # We might want to re-raise or handle gracefully depending on requirements.
        # For now, logging error is safer to avoid crashing app startup if Redis is down,
        # ensuring the app can still run (albeit without rate limiting or with errors on limit checks).
        pass
