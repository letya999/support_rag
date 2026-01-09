from typing import Dict, Any

class CacheHealthChecker:
    @staticmethod
    async def check_health(
        redis_connector,
        in_memory_cache,
        max_entries: int,
        ttl_seconds: int
    ) -> Dict[str, Any]:
        """
        Check cache health status.
        """
        try:
            if redis_connector.is_available():
                await redis_connector.ping()
                status = "healthy"
                backend = "redis"
                # For Redis, exact count is expensive using SCAN. 
                # We'll use DBSIZE if we could, but here we just return approximate or skip.
                # To match original behavior (which was expensive detailed count), 
                # we'll avoid the full scan here for performance reasons unless explicitly requested.
                # We'll return the in-memory count as a proxy or 0 if unknown.
                entry_count = "unknown (redis)" 
            else:
                status = "degraded"
                backend = "in-memory"
                entry_count = in_memory_cache.count()

            return {
                "status": status,
                "backend": backend,
                "total_entries": entry_count,
                "max_entries": max_entries,
                "ttl_seconds": ttl_seconds
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
