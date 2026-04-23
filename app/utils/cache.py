from threading import Lock
from time import monotonic
from typing import Generic, TypeVar


K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    def __init__(self, *, max_items: int, ttl_seconds: int):
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        self._store: dict[K, tuple[float, V]] = {}
        self._lock = Lock()

    def get(self, key: K) -> V | None:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None

            expires_at, value = item
            if expires_at <= monotonic():
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: K, value: V) -> None:
        with self._lock:
            self._prune_expired()
            if len(self._store) >= self.max_items:
                oldest_key = min(self._store, key=lambda candidate: self._store[candidate][0])
                self._store.pop(oldest_key, None)
            self._store[key] = (monotonic() + self.ttl_seconds, value)

    def delete(self, key: K) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _prune_expired(self) -> None:
        now = monotonic()
        expired_keys = [key for key, (expires_at, _) in self._store.items() if expires_at <= now]
        for key in expired_keys:
            self._store.pop(key, None)
