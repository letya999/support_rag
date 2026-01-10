
import sys
import os
import asyncio
from typing import Optional

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import settings
from redis import asyncio as aioredis

async def clear_redis_cache():
    """Clear all keys from the configured Redis database."""
    redis_url = settings.REDIS_URL
    print(f"🔌 Connecting to Redis at {redis_url}...")
    
    client = None
    try:
        client = await aioredis.from_url(redis_url, decode_responses=False)
        await client.ping()
    except Exception as e:
        print(f"⚠️  Failed to connect to {redis_url}: {e}")
        # Fallback to localhost
        localhost_url = "redis://localhost:6379/0"
        if redis_url != localhost_url:
             print(f"🔄 Retrying with localhost: {localhost_url}...")
             try:
                client = await aioredis.from_url(localhost_url, decode_responses=False)
                await client.ping()
             except Exception as e2:
                 print(f"❌ Error clearing Redis cache (localhost failed too): {e2}")
                 return
        else:
             return

    try:
        print("✅ Connected.")
        print("🧹 Flushing database...")
        await client.flushdb()
        print("✨ Redis cache cleared successfully.")
        await client.close()
    except Exception as e:
        print(f"❌ Error during flush: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(clear_redis_cache())
