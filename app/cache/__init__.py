"""
Cache module - DEPRECATED

⚠️ WARNING: This module is deprecated and maintained only for backward compatibility.

New code should import from:
- app.services.cache.manager import CacheManager, get_cache_manager
- app.services.cache.session import SessionManager
- app.nodes.check_cache, store_in_cache, cache_similarity

This file re-exports from the new locations to maintain compatibility
with existing code, but will be removed in a future version.
"""

import warnings

# Show deprecation warning
warnings.warn(
    "app.cache module is deprecated. "
    "Use 'from app.services.cache import ...' instead. "
    "This compatibility layer will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new locations for backward compatibility
# Import only non-circular dependencies at module level
from app.cache.models import CacheEntry, CacheStats
from app.cache.query_normalizer import QueryNormalizer
from app.cache.cache_stats import CacheMetrics

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    """Lazy import for CacheManager and related classes to avoid circular imports."""
    if name == "CacheManager":
        from app.services.cache.manager import CacheManager
        return CacheManager
    elif name == "get_cache_manager":
        from app.services.cache.manager import get_cache_manager
        return get_cache_manager
    elif name == "SessionManager":
        from app.services.cache.session import SessionManager
        return SessionManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "CacheEntry",
    "CacheStats",
    "CacheManager",
    "get_cache_manager",
    "SessionManager",
    "QueryNormalizer",
    "CacheMetrics",
]

