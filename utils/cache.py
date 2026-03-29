import hashlib
import time


class SearchCache:
    def __init__(self, ttl: int = 3600):
        self._cache: dict[str, tuple[float, list]] = {}
        self._ttl = ttl

    def _key(self, search_type: str, query: str) -> str:
        raw = f"{search_type}:{query}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, search_type: str, query: str) -> list | None:
        key = self._key(search_type, query)
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.time() - ts > self._ttl:
            del self._cache[key]
            return None
        return data

    def set(self, search_type: str, query: str, data: list):
        key = self._key(search_type, query)
        self._cache[key] = (time.time(), data)


cache = SearchCache()
