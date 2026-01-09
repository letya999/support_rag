from typing import Dict, Optional, Tuple
from app.services.cache.models import CacheEntry

class InMemoryCache:
    """
    In-memory cache with eviction policy based on hit count (LFU approximation).
    Acts as a fallback when Redis is unavailable.
    """
    def __init__(self, max_entries: int):
        self.max_entries = max_entries
        self._store: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[CacheEntry]:
        """Get entry from memory."""
        return self._store.get(key)

    def set(self, key: str, value: CacheEntry) -> None:
        """Set entry in memory and evict if needed."""
        self._store[key] = value
        self._evict_if_needed()

    def delete(self, key: str) -> bool:
        """Delete entry from memory."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all entries."""
        self._store.clear()

    def _evict_if_needed(self) -> None:
        """Evict the least frequently used item if capacity exceeded."""
        if len(self._store) > self.max_entries:
            # Remove entry with lowest hit count
            # Note: CacheEntry.hit_count is updated by the manager/user
            start_size = len(self._store)
            
            # Find item with min hit_count
            least_used_key: Optional[str] = None
            min_hits = float('inf')
            
            for k, v in self._store.items():
                if v.hit_count < min_hits:
                    min_hits = v.hit_count
                    least_used_key = k
            
            if least_used_key:
                del self._store[least_used_key]

    def get_all(self) -> Dict[str, CacheEntry]:
        """Return a copy of the store."""
        return self._store.copy()

    def count(self) -> int:
        """Return number of entries."""
        return len(self._store)
