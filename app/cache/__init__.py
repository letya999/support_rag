"""
Cache module for caching FAQ responses.

This module provides caching infrastructure for the support RAG pipeline:
- Query normalization (bilingual: Russian + English)
- Redis-based caching with LRU/TTL support
- Cache statistics and monitoring
- Integration with LangGraph pipeline
"""

from app.cache.models import CacheEntry, CacheStats
from app.cache.cache_layer import CacheManager, get_cache_manager
from app.cache.query_normalizer import QueryNormalizer
from app.cache.cache_stats import CacheMetrics

__all__ = [
    "CacheEntry",
    "CacheStats",
    "CacheManager",
    "get_cache_manager",
    "QueryNormalizer",
    "CacheMetrics",
]
