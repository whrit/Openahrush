"""
Cache backend implementation using Redis.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class CacheBackend:
    """
    Redis-backed cache backend for response caching.

    Provides async methods for cache operations with JSON serialization.
    """

    def __init__(
        self,
        redis_url: str,
        prefix: str = "cache:",
    ) -> None:
        """
        Initialize the cache backend.

        Args:
            redis_url: Redis connection URL.
            prefix: Key prefix for all cache keys.
        """
        self._client: Redis = Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._prefix = prefix

    def _make_key(self, key: str) -> str:
        """Add prefix to cache key."""
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> dict[str, Any] | None:
        """
        Get a cached value.

        Args:
            key: Cache key (without prefix).

        Returns:
            Cached value as dict, or None if not found or invalid.
        """
        full_key = self._make_key(key)
        try:
            data = await self._client.get(full_key)
            if data is None:
                return None
            return json.loads(data)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in cache for key: %s", full_key)
            return None
        except Exception as e:
            logger.error("Error getting cache key %s: %s", full_key, e)
            return None

    async def set(
        self,
        key: str,
        value: dict[str, Any],
        ttl: int,
    ) -> None:
        """
        Set a cached value with TTL.

        Args:
            key: Cache key (without prefix).
            value: Value to cache (will be JSON serialized).
            ttl: Time-to-live in seconds.
        """
        full_key = self._make_key(key)
        try:
            data = json.dumps(value)
            await self._client.setex(full_key, ttl, data)
        except Exception as e:
            logger.error("Error setting cache key %s: %s", full_key, e)

    async def delete(self, key: str) -> bool:
        """
        Delete a cached value.

        Args:
            key: Cache key (without prefix).

        Returns:
            True if key was deleted, False if not found.
        """
        full_key = self._make_key(key)
        try:
            result = await self._client.delete(full_key)
            return result > 0
        except Exception as e:
            logger.error("Error deleting cache key %s: %s", full_key, e)
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Uses SCAN to iterate through keys safely.

        Args:
            pattern: Pattern to match (without prefix).

        Returns:
            Number of keys deleted.
        """
        full_pattern = self._make_key(pattern)
        deleted = 0
        cursor = 0

        try:
            while True:
                cursor, keys = await self._client.scan(
                    cursor=cursor,
                    match=full_pattern,
                    count=100,
                )
                if keys:
                    await self._client.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.error("Error deleting cache pattern %s: %s", full_pattern, e)

        return deleted

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.

        Args:
            key: Cache key (without prefix).

        Returns:
            True if key exists, False otherwise.
        """
        full_key = self._make_key(key)
        try:
            result = await self._client.exists(full_key)
            return result > 0
        except Exception as e:
            logger.error("Error checking cache key %s: %s", full_key, e)
            return False

    async def close(self) -> None:
        """Close the Redis connection."""
        await self._client.close()
