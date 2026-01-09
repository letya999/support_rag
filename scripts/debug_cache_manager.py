
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.services.cache.manager import CacheManager
from app.services.cache.redis_client import RedisConnector

async def check_attributes():
    print("Checking CacheManager attributes...")
    # Mocking redis url
    try:
        cm = await CacheManager.create(redis_url="redis://localhost:6379/0", enable_stats=False)
        
        has_redis_client = hasattr(cm, 'redis_client')
        print(f"Has 'redis_client' attribute: {has_redis_client}")
        
        has_redis = hasattr(cm, 'redis')
        print(f"Has 'redis' attribute: {has_redis}")
        
        if has_redis:
            print(f"Type of 'redis' attribute: {type(cm.redis)}")
            has_client = hasattr(cm.redis, 'client')
            print(f"RedisConnector has 'client' attribute: {has_client}")
            
        await cm.close()
    except Exception as e:
        print(f"Error during check: {e}")

if __name__ == "__main__":
    asyncio.run(check_attributes())
