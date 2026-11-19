"""Small process-local caches for immutable generation inputs and outputs."""
from __future__ import annotations

import hashlib
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock
from time import monotonic


def file_digest(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BoundedCache:
    """LRU + TTL with a byte budget; never stores mutable DXF documents."""

    def __init__(self, max_bytes: int, max_entries: int, ttl: float, clock=monotonic):
        self.max_bytes, self.max_entries, self.ttl = max_bytes, max_entries, ttl
        self._clock = clock
        self._entries = OrderedDict()
        self._bytes = 0
        self._lock = RLock()
        self._flights = {}

    def _expire(self):
        now = self._clock()
        for key, (expiry, _value, size) in list(self._entries.items()):
            if expiry <= now:
                del self._entries[key]
                self._bytes -= size

    def get(self, key):
        with self._lock:
            self._expire()
            entry = self._entries.get(key)
            if entry is None:
                return None
            self._entries.move_to_end(key)
            return entry[1]

    def put(self, key, value, size: int):
        with self._lock:
            self._expire()
            previous = self._entries.pop(key, None)
            if previous:
                self._bytes -= previous[2]
            if size > self.max_bytes or self.max_entries <= 0 or self.ttl <= 0:
                return
            while self._entries and (self._bytes + size > self.max_bytes or len(self._entries) >= self.max_entries):
                _, (_, _, removed) = self._entries.popitem(last=False)
                self._bytes -= removed
            self._entries[key] = (self._clock() + self.ttl, value, size)
            self._bytes += size

    def clear(self):
        with self._lock:
            self._entries.clear()
            self._bytes = 0

    @contextmanager
    def single_flight(self, key):
        """Identical concurrent requests reuse one computation, not one document."""
        with self._lock:
            lock, users = self._flights.get(key, (Lock(), 0))
            self._flights[key] = (lock, users + 1)
        try:
            with lock:
                yield
        finally:
            with self._lock:
                _, users = self._flights[key]
                if users == 1:
                    del self._flights[key]
                else:
                    self._flights[key] = (lock, users - 1)
