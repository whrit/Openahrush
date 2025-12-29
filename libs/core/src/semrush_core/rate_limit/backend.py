"""
Redis-backed rate limiting backend using sliding window algorithm.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from semrush_core.rate_limit.config import EndpointCategory

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def build_rate_limit_key(category: EndpointCategory, identifier: str) -> str:
    """
    Build a rate limit key for Redis.

    Args:
        category: The endpoint category.
        identifier: User ID or IP address.

    Returns:
        Redis key string.
    """
    return f"ratelimit:{category.value}:{identifier}"


class RateLimitBackend:
    """
    Redis-backed rate limiter using sliding window log algorithm.

    Uses a sorted set to track request timestamps within the window.
    This provides more accurate rate limiting than token bucket for
    bursty traffic patterns.
    """

    def __init__(
        self,
        redis_url: str,
        prefix: str = "ratelimit:",
    ) -> None:
        """
        Initialize the rate limit backend.

        Args:
            redis_url: Redis connection URL.
            prefix: Key prefix for all rate limit keys.
        """
        self._client: Redis = Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._prefix = prefix

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Check if a request is allowed and record it.

        Uses sliding window log algorithm:
        1. Remove expired entries from the sorted set
        2. Count remaining entries
        3. If under limit, add current request
        4. Return result

        Args:
            key: Rate limit key (without prefix).
            limit: Maximum requests allowed in window.
            window_seconds: Time window in seconds.

        Returns:
            Tuple of (allowed, remaining, reset_timestamp).
        """
        now = time.time()
        window_start = now - window_seconds
        full_key = f"{self._prefix}{key}"

        try:
            # Use pipeline for atomicity
            pipe = self._client.pipeline()

            # Remove expired entries
            pipe.zremrangebyscore(full_key, 0, window_start)

            # Count current entries
            pipe.zcount(full_key, window_start, now)

            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1]

            if current_count >= limit:
                # Rate limited - don't add request
                remaining = 0
                reset_at = int(now + window_seconds)
                return False, remaining, reset_at

            # Add current request with timestamp as score
            request_id = f"{now}:{id(self)}"  # Unique identifier
            pipe2 = self._client.pipeline()
            pipe2.zadd(full_key, {request_id: now})
            pipe2.expire(full_key, window_seconds + 1)  # Slightly longer than window
            await pipe2.execute()

            remaining = max(0, limit - current_count - 1)
            reset_at = int(now + window_seconds)
            return True, remaining, reset_at

        except Exception as e:
            logger.error("Rate limit check failed for key %s: %s", key, e)
            # Fail open - allow request if Redis is down
            return True, limit - 1, int(time.time() + window_seconds)

    async def get_current_count(
        self,
        key: str,
        window_seconds: int,
    ) -> int:
        """
        Get the current request count in the window.

        Args:
            key: Rate limit key (without prefix).
            window_seconds: Time window in seconds.

        Returns:
            Current request count.
        """
        now = time.time()
        window_start = now - window_seconds
        full_key = f"{self._prefix}{key}"

        try:
            count = await self._client.zcount(full_key, window_start, now)
            return count
        except Exception as e:
            logger.error("Error getting rate limit count for key %s: %s", key, e)
            return 0

    async def close(self) -> None:
        """Close the Redis connection."""
        await self._client.close()
