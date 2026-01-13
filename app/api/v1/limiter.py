from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
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


# Rate limit configurations for internal network
# Adjusted for internal use - higher limits than public-facing APIs

# Standard rate limit for most endpoints (100 requests per minute)
standard_limiter = RateLimiter(times=100, seconds=60)

# Stricter limit for resource-intensive operations (20 requests per minute)
strict_limiter = RateLimiter(times=20, seconds=60)

# Very strict limit for critical operations (10 requests per minute)
critical_limiter = RateLimiter(times=10, seconds=60)
