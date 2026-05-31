"""
LRU cache for practice → home_region lookups.

The cache avoids a DB round-trip per request. TTL is configurable via
PRACTICE_CACHE_TTL_SECONDS. TTL=0 disables caching entirely.

Cache stores: { practice_id: (home_region, expires_at_timestamp) }
"""
import time
import logging
from collections import OrderedDict
from router_config import PRACTICE_CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)

_MAX_SIZE = 10_000  # max number of cached practice entries


class PracticeRegionCache:
    def __init__(self, ttl: int = PRACTICE_CACHE_TTL_SECONDS, max_size: int = _MAX_SIZE):
        self.ttl = ttl
        self.max_size = max_size
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()

    def get(self, practice_id: str) -> str | None:
        """Return cached home_region or None if missing/expired."""
        if self.ttl == 0:
            return None
        entry = self._cache.get(practice_id)
        if entry is None:
            return None
        home_region, expires_at = entry
        if time.monotonic() > expires_at:
            del self._cache[practice_id]
            logger.debug("practice_cache_expired", extra={"practice_id": practice_id})
            return None
        # Move to end (LRU)
        self._cache.move_to_end(practice_id)
        return home_region

    def set(self, practice_id: str, home_region: str) -> None:
        """Cache a practice → home_region mapping."""
        if self.ttl == 0:
            return
        if practice_id in self._cache:
            self._cache.move_to_end(practice_id)
        elif len(self._cache) >= self.max_size:
            evicted = self._cache.popitem(last=False)
            logger.debug("practice_cache_evicted", extra={"practice_id": evicted[0]})
        expires_at = time.monotonic() + self.ttl
        self._cache[practice_id] = (home_region, expires_at)

    def invalidate(self, practice_id: str) -> None:
        """Remove a specific entry from the cache."""
        self._cache.pop(practice_id, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


# Module-level singleton
practice_cache = PracticeRegionCache()
