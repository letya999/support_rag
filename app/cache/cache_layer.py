"""
DEPRECATED: app/cache/cache_layer.py

This file has been moved to app/services/cache/manager.py

This stub exists only for backward compatibility.
Please update your imports to use:
    from app.services.cache.manager import CacheManager, get_cache_manager
"""

import warnings

warnings.warn(
    "Importing from app.cache.cache_layer is deprecated. "
    "Use 'from app.services.cache.manager import CacheManager, get_cache_manager' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from new location
from app.services.cache.manager import (
    CacheManager,
    get_cache_manager,
    # Export any other functions/classes that were in cache_layer
)

__all__ = [
    "CacheManager",
    "get_cache_manager",
]
