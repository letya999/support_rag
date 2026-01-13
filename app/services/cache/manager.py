"""
Cache Manager: Coordination layer for FAQ responses.

Refactored to separate concerns:
- Redis communication -> redis_client.py
- In-memory fallback -> eviction_policy.py
- Health checks -> health_checker.py
"""

import json
from typing import Optional, Dict, Any, List
from app.logging_config import logger
from app.services.cache.models import CacheEntry
from app.services.cache.stats import CacheMetrics
from app.services.cache.redis_client import RedisConnector
from app.services.cache.eviction_policy import InMemoryCache
from app.services.cache.health_checker import CacheHealthChecker

class CacheManager:
    """
    Redis-based cache manager for FAQ responses with in-memory fallback.
    """

    def __init__(
        self,
        redis_connector: RedisConnector,
        max_entries: int = 1000,
        ttl_seconds: int = 86400,  # 24 hours
        enable_stats: bool = True
    ):
        self.redis = redis_connector
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        
        self.memory = InMemoryCache(max_entries)
        self.metrics = CacheMetrics() if enable_stats else None
        
        self.cache_prefix = "faq_cache:"

    @classmethod
    async def create(
        cls,
        redis_url: str = "redis://localhost:6379/0",
        max_entries: int = 1000,
        ttl_seconds: int = 86400,
        enable_stats: bool = True
    ) -> "CacheManager":
        """
        Create a cache manager with Redis connection.
        """
        connector = RedisConnector(redis_url)
        await connector.connect()
        
        return cls(
            redis_connector=connector,
            max_entries=max_entries,
            ttl_seconds=ttl_seconds,
            enable_stats=enable_stats
        )

    async def set(self, query_normalized: str, entry: CacheEntry) -> bool:
        """Store a cache entry."""
        try:
            # Serialize
            entry_json = entry.model_dump_json()

            if self.redis.is_available():
                await self.redis.setex(
                    f"{self.cache_prefix}{query_normalized}",
                    self.ttl_seconds,
                    entry_json
                )
            else:
                self.memory.set(query_normalized, entry)

            return True
        except Exception as e:
            logger.error("Cache set failed", extra={"query": query_normalized, "error": str(e)})
            return False

    async def get(self, query_normalized: str) -> Optional[CacheEntry]:
        """Retrieve a cache entry."""
        try:
            if self.redis.is_available():
                data = await self.redis.get(f"{self.cache_prefix}{query_normalized}")
                if data:
                    entry = CacheEntry.model_validate_json(data)
                    entry.hit_count += 1
                    # Update hit count in Redis to prolong life? 
                    # Original logic: entry.hit_count += 1, then set() back.
                    await self.set(query_normalized, entry)
                    return entry
            else:
                entry = self.memory.get(query_normalized)
                if entry:
                    entry.hit_count += 1
                    return entry
            return None
        except Exception as e:
            logger.error("Cache get failed", extra={"query": query_normalized, "error": str(e)})
            return None

    async def delete(self, query_normalized: str) -> bool:
        """Delete a cache entry."""
        try:
            if self.redis.is_available():
                result = await self.redis.delete(f"{self.cache_prefix}{query_normalized}")
                return result > 0
            else:
                return self.memory.delete(query_normalized)
        except Exception as e:
            logger.error("Cache delete failed", extra={"query": query_normalized, "error": str(e)})
            return False

    async def clear(self) -> bool:
        """Clear all cache entries."""
        try:
            if self.redis.is_available():
                # This logic is a bit complex to delegate completely to basic connector without specific scan logic
                # We reused scan in connector
                pattern = f"{self.cache_prefix}*"
                cursor = 0
                while True:
                    cursor, keys = await self.redis.scan(cursor, match=pattern)
                    if keys:
                        await self.redis.delete(*keys)
                    if cursor == 0:
                        break
            else:
                self.memory.clear()
            return True
        except Exception as e:
            logger.error("Cache clear failed", extra={"error": str(e)})
            return False

    async def get_all_entries(self) -> Dict[str, CacheEntry]:
        """Get all cache entries."""
        try:
            entries = {}
            if self.redis.is_available():
                pattern = f"{self.cache_prefix}*"
                cursor = 0
                while True:
                    cursor, keys = await self.redis.scan(cursor, match=pattern)
                    for key in keys:
                        data = await self.redis.get(key)
                        if data:
                            query = key.decode() if isinstance(key, bytes) else key
                            query = query.replace(self.cache_prefix, "", 1)
                            entry = CacheEntry.model_validate_json(data)
                            entries[query] = entry
                    if cursor == 0:
                        break
            else:
                entries = self.memory.get_all()
            return entries
        except Exception as e:
            logger.error("Get all entries failed", extra={"error": str(e)})
            return {}

    def get_stats(self) -> Optional[Dict[str, Any]]:
        """Get cache statistics."""
        if not self.metrics:
            return None

        # Approximate count
        entry_count = self.memory.count()
        if self.redis.is_available():
             # We don't verify count on Redis for performance, just use memory valid count or 0?
             # Original code used memory count as fallback.
             pass

        self.metrics.update_total_entries(entry_count)
        return self.metrics.get_stats()

    async def close(self):
        """Close Redis connection."""
        await self.redis.close()

    async def health_check(self) -> Dict[str, Any]:
        """Check cache health status."""
        return await CacheHealthChecker.check_health(
            self.redis,
            self.memory,
            self.max_entries,
            self.ttl_seconds
        )


# Global instance management
from app.settings import settings
from app.services.config_loader.loader import get_cache_config

_cache_instance = None


async def get_cache_manager(
    redis_url: Optional[str] = None,
    max_entries: Optional[int] = None,
    ttl_seconds: Optional[int] = None,
    enable_stats: Optional[bool] = None
) -> CacheManager:
    """
    Get or create the global cache manager instance.
    """
    global _cache_instance
    if _cache_instance is None:
        cache_config = get_cache_config()
        
        final_redis_url = redis_url or cache_config.get("redis_url") or settings.REDIS_URL
        final_max_entries = max_entries if max_entries is not None else cache_config.get("max_entries", 1000)
        final_ttl_seconds = ttl_seconds if ttl_seconds is not None else cache_config.get("ttl_seconds", 86400)
        final_enable_stats = enable_stats if enable_stats is not None else cache_config.get("enable_stats", True)

        _cache_instance = await CacheManager.create(
            redis_url=final_redis_url,
            max_entries=final_max_entries,
            ttl_seconds=final_ttl_seconds,
            enable_stats=final_enable_stats
        )
    return _cache_instance
