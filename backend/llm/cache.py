"""
Per-call cache.

Keyed by call_id (Retell call identifier). Stores patient/provider/hours
data fetched during a call so we don't hit MongoDB or external APIs
repeatedly within the same call. TTL'd; entries auto-expire.

Designed to be safe in a single-process FastAPI deployment. For multi-pod
deployments, swap this for Redis (the public API stays the same).
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Any
from threading import RLock


@dataclass
class _Entry:
    value: Any
    expires_at: float


class CallCache:
    """Per-call key/value cache with TTL-based eviction."""

    def __init__(self, default_ttl_seconds: int = 1800):
        # Outer dict: call_id → inner dict: key → _Entry
        self._store: dict[str, dict[str, _Entry]] = {}
        self._lock = RLock()
        self.default_ttl = default_ttl_seconds
        self._stats: dict[str, int] = {"hits": 0, "misses": 0, "sets": 0, "evictions": 0}

    # ── Core API ──────────────────────────────────────────────────────

    def get(self, call_id: str, key: str) -> tuple[bool, Any]:
        """Returns (hit, value). hit=False means miss or expired."""
        with self._lock:
            self._evict_expired(call_id)
            entry = self._store.get(call_id, {}).get(key)
            if entry is None:
                self._stats["misses"] += 1
                return False, None
            self._stats["hits"] += 1
            return True, entry.value

    def set(self, call_id: str, key: str, value: Any, ttl: int | None = None) -> None:
        with self._lock:
            ttl = ttl or self.default_ttl
            self._store.setdefault(call_id, {})[key] = _Entry(
                value=value, expires_at=time.time() + ttl,
            )
            self._stats["sets"] += 1

    def get_or_set(self, call_id: str, key: str, factory, ttl: int | None = None):
        """Returns cached value if present, otherwise calls `factory()` and caches it."""
        hit, value = self.get(call_id, key)
        if hit:
            return value
        value = factory()
        self.set(call_id, key, value, ttl=ttl)
        return value

    def invalidate(self, call_id: str, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._store.pop(call_id, None)
            elif call_id in self._store:
                self._store[call_id].pop(key, None)

    def end_call(self, call_id: str) -> None:
        """Drop everything for a call_id (hook for Retell call_ended webhook)."""
        self.invalidate(call_id)

    # ── Bookkeeping ───────────────────────────────────────────────────

    def _evict_expired(self, call_id: str) -> None:
        now = time.time()
        bucket = self._store.get(call_id)
        if not bucket:
            return
        expired = [k for k, e in bucket.items() if e.expires_at <= now]
        for k in expired:
            bucket.pop(k, None)
            self._stats["evictions"] += 1
        if not bucket:
            self._store.pop(call_id, None)

    def stats(self) -> dict:
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total) if total else 0.0
            return {
                **self._stats,
                "active_calls": len(self._store),
                "hit_rate": round(hit_rate, 4),
            }


# Singleton
_cache: CallCache | None = None


def get_call_cache() -> CallCache:
    global _cache
    if _cache is None:
        _cache = CallCache()
    return _cache


def reset_call_cache_for_tests() -> None:
    global _cache
    _cache = None
