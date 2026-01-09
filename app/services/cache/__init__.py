"""
Cache service module.

This module provides caching functionality for the RAG pipeline:
- CacheManager: Core cache operations (Redis + Qdrant semantic cache)
- SessionManager: Session management and persistence
- Similarity: Semantic similarity checking for cache

This is a refactored version from app/cache/ to follow the
services pattern (business logic) + nodes pattern (wrappers).
"""

from .manager import CacheManager, get_cache_manager
from .session_manager import SessionManager
from .similarity import (
    check_semantic_similarity,
    store_in_semantic_cache,
    ensure_semantic_cache_collection,
    cleanup_expired_semantic_cache,
    get_similarity_threshold,
    get_ttl_seconds
)

__all__ = [
    "CacheManager",
    "get_cache_manager",
    "SessionManager",
    "check_semantic_similarity",
    "store_in_semantic_cache",
    "ensure_semantic_cache_collection",
    "cleanup_expired_semantic_cache",
    "get_similarity_threshold",
    "get_ttl_seconds",
]
