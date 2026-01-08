"""
DEPRECATED: app/cache/nodes.py

Cache nodes have been refactored into separate modules:
- app/nodes/check_cache/
- app/nodes/store_in_cache/  
- app/nodes/cache_similarity/

This stub exists only for backward compatibility.
Please update your imports to use:
    from app.nodes.check_cache.node import check_cache_node
    from app.nodes.store_in_cache.node import store_in_cache_node
    from app.nodes.cache_similarity.node import cache_similarity_node
"""

import warnings

warnings.warn(
    "Importing from app.cache.nodes is deprecated. "
    "Use individual node imports from app.nodes.* instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new locations
from app.nodes.check_cache.node import check_cache_node
from app.nodes.store_in_cache.node import store_in_cache_node
from app.nodes.cache_similarity.node import cache_similarity_node

__all__ = [
    "check_cache_node",
    "store_in_cache_node",
    "cache_similarity_node",
]
