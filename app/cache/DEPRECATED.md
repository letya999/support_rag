# DEPRECATED: app/cache

⚠️ **This directory is deprecated and will be removed in a future version.**

## Migration Guide

### Old Import (Deprecated)
```python
from app.cache.cache_layer import CacheManager, get_cache_manager
from app.cache.session_manager import SessionManager
from app.cache.nodes import check_cache_node, store_in_cache_node
```

### New Import (Recommended)
```python
# Services (business logic)
from app.services.cache.manager import CacheManager, get_cache_manager
from app.services.cache.session import SessionManager
from app.services.cache.similarity import check_semantic_similarity

# Nodes (LangGraph wrappers)
from app.nodes.check_cache.node import check_cache_node
from app.nodes.store_in_cache.node import store_in_cache_node
from app.nodes.cache_similarity.node import cache_similarity_node
```

## What Changed?

Following the architectural refactoring (see `MASTER_PLAN.md`), cache functionality was split into:

1. **`app/services/cache/`** - Core business logic
   - `manager.py` - CacheManager (Redis operations)
   - `session.py` - SessionManager (session persistence)
   - `similarity.py` - Semantic similarity functions

2. **`app/nodes/*/`** - LangGraph node wrappers
   - `check_cache/` - Exact match cache lookup
   - `store_in_cache/` - Store results in cache
   - `cache_similarity/` - Optional semantic similarity search

## Backward Compatibility

For now, `app/cache/__init__.py` re-exports from the new locations to maintain compatibility.
However, this compatibility layer will be removed in a future version.

**Action Required:** Update your imports to use the new paths.

## Files Status

- ✅ `models.py` - Still used (cache data models)
- ✅ `query_normalizer.py` - Still used (query preprocessing)
- ✅ `cache_stats.py` - Still used (statistics)
- ⚠️ `cache_layer.py` - DEPRECATED, use `services/cache/manager.py`
- ⚠️ `session_manager.py` - DEPRECATED, use `services/cache/session.py`
- ⚠️ `nodes.py` - DEPRECATED, use individual nodes in `app/nodes/`

## Timeline

- **Phase 1 (Current):** Deprecation warnings, backward compatibility maintained
- **Phase 2 (Future):** Remove deprecated files
- **Phase 3 (Future):** Remove `app/cache/` directory entirely
