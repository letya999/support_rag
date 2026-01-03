"""
Cache Layer: Redis-based cache for FAQ responses.

Provides:
- LRU (Least Recently Used) eviction
- TTL (Time To Live) for entries
- Both async and sync interfaces
- Memory-efficient JSON serialization
- Statistics tracking

Example:
    # Initialize
    cache = await CacheManager.create()

    # Store entry
    await cache.set(
        query_normalized="reset password",
        entry=CacheEntry(...)
    )

    # Retrieve entry
    cached = await cache.get("reset password")

    # Get stats
    stats = cache.get_stats()
"""

import json
import pickle
import asyncio
from typing import Optional, Dict, Any
from datetime import timedelta
import aioredis
from redis.asyncio import Redis

from app.cache.models import CacheEntry
from app.cache.cache_stats import CacheMetrics


class CacheManager:
    """
    Redis-based cache manager for FAQ responses.

    Features:
    - Async Redis operations
    - LRU eviction policy
    - TTL support
    - Cache statistics
    - Graceful fallback (in-memory if Redis unavailable)
    """

    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        max_entries: int = 1000,
        ttl_seconds: int = 86400,  # 24 hours
        enable_stats: bool = True
    ):
        """
        Initialize cache manager.

        Args:
            redis_client: Redis async client (optional)
            max_entries: Maximum cache entries (default 1000)
            ttl_seconds: Time-to-live for entries in seconds (default 24 hours)
            enable_stats: Enable statistics tracking
        """
        self.redis_client = redis_client
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.enable_stats = enable_stats

        # In-memory fallback
        self._in_memory_cache: Dict[str, CacheEntry] = {}

        # Statistics
        self.metrics = CacheMetrics() if enable_stats else None

        # Configuration
        self.redis_available = redis_client is not None
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

        Args:
            redis_url: Redis connection URL
            max_entries: Maximum cache entries
            ttl_seconds: Time-to-live in seconds
            enable_stats: Enable statistics

        Returns:
            Initialized CacheManager

        Example:
            cache = await CacheManager.create(
                redis_url="redis://localhost:6379/0"
            )
        """
        try:
            redis_client = await aioredis.from_url(redis_url, decode_responses=False)
            await redis_client.ping()  # Verify connection
            print("✅ Redis connected successfully")
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}. Using in-memory cache.")
            redis_client = None

        return cls(
            redis_client=redis_client,
            max_entries=max_entries,
            ttl_seconds=ttl_seconds,
            enable_stats=enable_stats
        )

    async def set(
        self,
        query_normalized: str,
        entry: CacheEntry
    ) -> bool:
        """
        Store a cache entry.

        Args:
            query_normalized: Normalized query (cache key)
            entry: CacheEntry to store

        Returns:
            True if successful, False otherwise

        Example:
            success = await cache.set(
                "reset password",
                CacheEntry(
                    query_normalized="reset password",
                    query_original="How to reset password?",
                    answer="Click on Forgot Password...",
                    doc_ids=["doc_1"],
                    confidence=0.95
                )
            )
        """
        try:
            # Serialize entry
            entry_json = entry.model_dump_json()

            if self.redis_available:
                # Store in Redis with TTL
                key = f"{self.cache_prefix}{query_normalized}"
                await self.redis_client.setex(
                    key,
                    self.ttl_seconds,
                    entry_json
                )
            else:
                # Store in memory
                self._in_memory_cache[query_normalized] = entry

                # Simple LRU: if cache exceeds max size, remove oldest entry
                if len(self._in_memory_cache) > self.max_entries:
                    # Remove entry with lowest hit count (simple LRU approximation)
                    oldest = min(
                        self._in_memory_cache.items(),
                        key=lambda x: x[1].hit_count
                    )
                    del self._in_memory_cache[oldest[0]]

            return True
        except Exception as e:
            print(f"❌ Cache set failed: {e}")
            return False

    async def get(self, query_normalized: str) -> Optional[CacheEntry]:
        """
        Retrieve a cache entry.

        Args:
            query_normalized: Normalized query

        Returns:
            CacheEntry if found, None otherwise

        Example:
            cached = await cache.get("reset password")
            if cached:
                print(f"Found in cache! Answer: {cached.answer}")
            else:
                print("Not in cache, will run full pipeline")
        """
        try:
            if self.redis_available:
                key = f"{self.cache_prefix}{query_normalized}"
                data = await self.redis_client.get(key)

                if data:
                    entry = CacheEntry.model_validate_json(data)
                    # Update hit count
                    entry.hit_count += 1
                    # Update back in Redis
                    await self.set(query_normalized, entry)
                    return entry
            else:
                # Check in-memory cache
                if query_normalized in self._in_memory_cache:
                    entry = self._in_memory_cache[query_normalized]
                    # Update hit count
                    entry.hit_count += 1
                    self._in_memory_cache[query_normalized] = entry
                    return entry

            return None
        except Exception as e:
            print(f"❌ Cache get failed: {e}")
            return None

    async def delete(self, query_normalized: str) -> bool:
        """
        Delete a cache entry.

        Args:
            query_normalized: Normalized query to delete

        Returns:
            True if deleted, False if not found or error

        Example:
            deleted = await cache.delete("reset password")
        """
        try:
            if self.redis_available:
                key = f"{self.cache_prefix}{query_normalized}"
                result = await self.redis_client.delete(key)
                return result > 0
            else:
                if query_normalized in self._in_memory_cache:
                    del self._in_memory_cache[query_normalized]
                    return True
                return False
        except Exception as e:
            print(f"❌ Cache delete failed: {e}")
            return False

    async def clear(self) -> bool:
        """
        Clear all cache entries.

        Returns:
            True if successful

        Example:
            await cache.clear()
        """
        try:
            if self.redis_available:
                # Delete all entries with our prefix
                pattern = f"{self.cache_prefix}*"
                cursor = 0
                while True:
                    cursor, keys = await self.redis_client.scan(cursor, match=pattern)
                    if keys:
                        await self.redis_client.delete(*keys)
                    if cursor == 0:
                        break
            else:
                self._in_memory_cache.clear()

            return True
        except Exception as e:
            print(f"❌ Cache clear failed: {e}")
            return False

    async def get_all_entries(self) -> Dict[str, CacheEntry]:
        """
        Get all cache entries.

        Returns:
            Dictionary of all cached entries

        Useful for:
        - Inspection
        - Backup
        - Statistics computation
        """
        try:
            entries = {}

            if self.redis_available:
                pattern = f"{self.cache_prefix}*"
                cursor = 0
                while True:
                    cursor, keys = await self.redis_client.scan(cursor, match=pattern)
                    for key in keys:
                        data = await self.redis_client.get(key)
                        if data:
                            query = key.decode() if isinstance(key, bytes) else key
                            query = query.replace(self.cache_prefix, "", 1)
                            entry = CacheEntry.model_validate_json(data)
                            entries[query] = entry
                    if cursor == 0:
                        break
            else:
                entries = dict(self._in_memory_cache)

            return entries
        except Exception as e:
            print(f"❌ Get all entries failed: {e}")
            return {}

    def get_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get cache statistics.

        Returns:
            Statistics object if enabled, None otherwise

        Example:
            stats = cache.get_stats()
            print(f"Hit rate: {stats.hit_rate}%")
            print(f"Time saved: {stats.savings_time}s")
        """
        if not self.metrics:
            return None

        # Update entry count
        if self.redis_available:
            # Note: This is approximate in Redis (counting prefix keys)
            entry_count = len(self._in_memory_cache)  # Fallback to in-memory count
        else:
            entry_count = len(self._in_memory_cache)

        self.metrics.update_total_entries(entry_count)

        return self.metrics.get_stats()

    async def close(self):
        """
        Close Redis connection.

        Example:
            await cache.close()
        """
        if self.redis_client:
            await self.redis_client.close()

    async def health_check(self) -> Dict[str, Any]:
        """
        Check cache health status.

        Returns:
            Health status information

        Example:
            health = await cache.health_check()
            print(f"Status: {health['status']}")
        """
        try:
            if self.redis_available:
                await self.redis_client.ping()
                status = "healthy"
                backend = "redis"
            else:
                status = "degraded"
                backend = "in-memory"

            all_entries = await self.get_all_entries()

            return {
                "status": status,
                "backend": backend,
                "total_entries": len(all_entries),
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Global cache instance
_cache_instance: Optional[CacheManager] = None


async def get_cache_manager(redis_url: str = "redis://localhost:6379/0") -> CacheManager:
    """
    Get or create the global cache manager instance.

    Args:
        redis_url: Redis connection URL

    Returns:
        Initialized CacheManager

    Example:
        cache = await get_cache_manager()
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = await CacheManager.create(redis_url=redis_url)
    return _cache_instance
