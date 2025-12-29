"""
Distributed lock implementation using Redis.
"""

from __future__ import annotations

import logging
from enum import Enum

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class JobType(str, Enum):
    """Types of jobs that can be locked."""

    CRAWL = "crawl"
    EXPORT = "export"
    CC_INGESTION = "cc_ingestion"


class DistributedLock:
    """
    Redis-based distributed lock implementation.

    Provides mutual exclusion across multiple processes/servers.
    Uses Redis SET with NX (not exists) and EX (expiry) for atomicity.
    """

    def __init__(
        self,
        redis_url: str,
        prefix: str = "lock:",
    ) -> None:
        """
        Initialize the distributed lock.

        Args:
            redis_url: Redis connection URL.
            prefix: Key prefix for all lock keys.
        """
        self._client: Redis = Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._prefix = prefix

    def _make_key(self, key: str) -> str:
        """Add prefix to lock key."""
        return f"{self._prefix}{key}"

    async def acquire(
        self,
        key: str,
        owner: str,
        ttl_seconds: int,
    ) -> bool:
        """
        Attempt to acquire a lock.

        Args:
            key: Lock key (without prefix).
            owner: Identifier of the lock owner (e.g., worker ID).
            ttl_seconds: Lock expiration time in seconds.

        Returns:
            True if lock was acquired, False if already held.
        """
        full_key = self._make_key(key)
        try:
            # SET with NX (only if not exists) and EX (expiry)
            result = await self._client.set(
                full_key,
                owner,
                nx=True,
                ex=ttl_seconds,
            )
            acquired = result is not None
            if acquired:
                logger.debug("Lock acquired: %s by %s", key, owner)
            else:
                logger.debug("Lock not available: %s", key)
            return acquired
        except Exception as e:
            logger.error("Error acquiring lock %s: %s", key, e)
            return False

    async def release(
        self,
        key: str,
        owner: str,
    ) -> bool:
        """
        Release a lock if owned by the specified owner.

        Uses a check-and-delete pattern to ensure only the owner can release.

        Args:
            key: Lock key (without prefix).
            owner: Identifier of the expected lock owner.

        Returns:
            True if lock was released, False if not owned or not found.
        """
        full_key = self._make_key(key)
        try:
            # Check if we own the lock
            current_owner = await self._client.get(full_key)
            if current_owner is None:
                logger.debug("Lock not found for release: %s", key)
                return False

            if current_owner != owner:
                logger.warning(
                    "Lock release denied: %s owned by %s, not %s",
                    key,
                    current_owner,
                    owner,
                )
                return False

            # Delete the lock
            result = await self._client.delete(full_key)
            released = result > 0
            if released:
                logger.debug("Lock released: %s by %s", key, owner)
            return released
        except Exception as e:
            logger.error("Error releasing lock %s: %s", key, e)
            return False

    async def is_locked(self, key: str) -> bool:
        """
        Check if a lock is currently held.

        Args:
            key: Lock key (without prefix).

        Returns:
            True if lock exists, False otherwise.
        """
        full_key = self._make_key(key)
        try:
            result = await self._client.exists(full_key)
            return result > 0
        except Exception as e:
            logger.error("Error checking lock %s: %s", key, e)
            return False

    async def get_owner(self, key: str) -> str | None:
        """
        Get the current owner of a lock.

        Args:
            key: Lock key (without prefix).

        Returns:
            Owner identifier, or None if not locked.
        """
        full_key = self._make_key(key)
        try:
            owner = await self._client.get(full_key)
            return owner
        except Exception as e:
            logger.error("Error getting lock owner %s: %s", key, e)
            return None

    async def refresh(
        self,
        key: str,
        owner: str,
        ttl_seconds: int,
    ) -> bool:
        """
        Extend the TTL of a lock if owned.

        Args:
            key: Lock key (without prefix).
            owner: Expected lock owner.
            ttl_seconds: New TTL in seconds.

        Returns:
            True if TTL was extended, False if not owned or not found.
        """
        full_key = self._make_key(key)
        try:
            # Check ownership first
            current_owner = await self._client.get(full_key)
            if current_owner is None or current_owner != owner:
                return False

            result = await self._client.expire(full_key, ttl_seconds)
            return result
        except Exception as e:
            logger.error("Error refreshing lock %s: %s", key, e)
            return False

    async def close(self) -> None:
        """Close the Redis connection."""
        await self._client.close()
