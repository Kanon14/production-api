"""
Response Cache
--------------
Simple in-memory response cache with TTL support.

Purpose:
- Avoid repeated LLM calls for the same user query
- Reduce latency for repeated questions
- Reduce API cost during development/testing

Current implementation:
- Uses Python dictionary in memory
- Supports TTL, meaning cached responses expire after a fixed time
- Tracks cache hits, misses, hit rate, and active cached entries

Production note:
- This is suitable for local development or single-instance deployment.
- For multi-instance production, replace this with Redis later.
"""

import hashlib
import time
from typing import Optional


class ResponseCache:
    """
    In-memory response cache with TTL.

    Args:
        ttl_seconds:
            How long each cached response should remain valid.
            Default is 300 seconds, equal to 5 minutes.

    Example:
        cache = ResponseCache(ttl_seconds=300)

        cached = cache.get("What is RAG?")
        if cached:
            return cached

        response = call_llm("What is RAG?")
        cache.set("What is RAG?", response)
        return response
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        # Time-to-live for each cached response.
        self.ttl = ttl_seconds

        # Internal cache storage.
        # Key: hashed normalized query
        # Value: dictionary containing response, timestamp, and original query
        self._cache: dict[str, dict] = {}

        # Cache performance counters.
        self._hits = 0
        self._misses = 0

    def _make_key(self, query: str) -> str:
        """
        Create a stable cache key from the user query.

        The query is normalized before hashing so similar queries with different
        capitalization or surrounding spaces map to the same cache key.

        Example:
            "What is Python?"
            " what is python? "

        Both produce the same cache key.

        Args:
            query: Raw user query.

        Returns:
            SHA-256 hash string used as the cache key.
        """
        normalized_query = query.lower().strip()
        return hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()

    def get(self, query: str) -> Optional[str]:
        """
        Get cached response if it exists and has not expired.

        Args:
            query: User query.

        Returns:
            Cached response string if available and valid.
            None if the cache misses or the entry has expired.
        """
        key = self._make_key(query)
        entry = self._cache.get(key)

        # Case 1: Cache key does not exist.
        if entry is None:
            self._misses += 1
            return None

        # Case 2: Cache key exists, but the entry has expired.
        current_time = time.time()
        age = current_time - entry["timestamp"]

        if age >= self.ttl:
            del self._cache[key]
            self._misses += 1
            return None

        # Case 3: Cache key exists and is still valid.
        self._hits += 1
        return entry["response"]

    def set(self, query: str, response: str) -> None:
        """
        Store a response in the cache.

        Args:
            query: User query.
            response: LLM or pipeline response to cache.

        Returns:
            None
        """
        key = self._make_key(query)

        self._cache[key] = {
            "response": response,
            "timestamp": time.time(),
            "query": query,
        }

    def clear_expired(self) -> int:
        """
        Remove expired cache entries.

        This is optional because expired entries are already removed during get().
        However, this method is useful if you want to clean up memory manually.

        Returns:
            Number of expired entries removed.
        """
        current_time = time.time()
        expired_keys = []

        for key, entry in self._cache.items():
            age = current_time - entry["timestamp"]

            if age >= self.ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

        return len(expired_keys)

    def clear(self) -> None:
        """
        Clear all cached responses and reset cache storage.

        This does not reset hit/miss statistics.
        """
        self._cache.clear()

    @property
    def stats(self) -> dict:
        """
        Return cache performance statistics.

        Returns:
            Dictionary containing:
            - hits: Number of successful cache reads
            - misses: Number of failed cache reads
            - hit_rate: Percentage of cache reads that were hits
            - cached_entries: Number of currently stored cache entries
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1%}",
            "cached_entries": len(self._cache),
        }