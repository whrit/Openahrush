"""
Job limiter for concurrent job caps.

Uses Redis sets to track active jobs per project and enforce limits.
"""

from __future__ import annotations

import logging
import uuid
from typing import cast

from redis.asyncio import Redis

from semrush_core.locks.config import JobLimitsConfig

logger = logging.getLogger(__name__)


def build_crawl_slot_key(project_id: str) -> str:
    """Build Redis key for crawl slots."""
    return f"jobs:crawl:{project_id}"


def build_export_slot_key(project_id: str) -> str:
    """Build Redis key for export slots."""
    return f"jobs:export:{project_id}"


def build_cc_ingestion_key() -> str:
    """Build Redis key for global CC ingestion lock."""
    return "jobs:cc_ingestion:global"


class JobLimiter:
    """
    Manages concurrent job limits using Redis.

    Uses different strategies for different job types:
    - Crawl/Export: Redis sets to track active jobs per project
    - CC Ingestion: Single global lock
    """

    def __init__(
        self,
        redis_url: str,
        config: JobLimitsConfig | None = None,
    ) -> None:
        """
        Initialize the job limiter.

        Args:
            redis_url: Redis connection URL.
            config: Job limits configuration.
        """
        self._client: Redis = Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._config = config or JobLimitsConfig()

    async def acquire_crawl_slot(
        self,
        project_id: str,
    ) -> tuple[bool, str | None]:
        """
        Acquire a crawl slot for a project.

        Args:
            project_id: The project ID.

        Returns:
            Tuple of (acquired, job_id). Job ID is None if not acquired.
        """
        key = build_crawl_slot_key(project_id)
        limit = self._config.max_concurrent_crawls_per_project
        ttl = self._config.crawl_lock_ttl_seconds

        try:
            # Check current count
            # redis-py type stubs incorrectly show union type for async methods
            current_count = cast(int, await self._client.scard(key))  # type: ignore[misc]
            if current_count >= limit:
                logger.debug(
                    "Crawl slot denied for project %s: %d/%d active",
                    project_id,
                    current_count,
                    limit,
                )
                return False, None

            # Generate unique job ID
            job_id = str(uuid.uuid4())

            # Add to set
            await self._client.sadd(key, job_id)  # type: ignore[misc]
            await self._client.expire(key, ttl)

            logger.debug(
                "Crawl slot acquired for project %s: job %s",
                project_id,
                job_id,
            )
            return True, job_id
        except Exception as e:
            logger.error("Error acquiring crawl slot for %s: %s", project_id, e)
            return False, None

    async def release_crawl_slot(
        self,
        project_id: str,
        job_id: str,
    ) -> bool:
        """
        Release a crawl slot.

        Args:
            project_id: The project ID.
            job_id: The job ID to release.

        Returns:
            True if released, False otherwise.
        """
        key = build_crawl_slot_key(project_id)
        try:
            result = cast(int, await self._client.srem(key, job_id))  # type: ignore[misc]
            released = result > 0
            if released:
                logger.debug(
                    "Crawl slot released for project %s: job %s",
                    project_id,
                    job_id,
                )
            return released
        except Exception as e:
            logger.error("Error releasing crawl slot for %s: %s", project_id, e)
            return False

    async def get_active_crawls(self, project_id: str) -> int:
        """Get count of active crawls for a project."""
        key = build_crawl_slot_key(project_id)
        try:
            count = cast(int, await self._client.scard(key))  # type: ignore[misc]
            return count
        except Exception as e:
            logger.error("Error getting active crawls for %s: %s", project_id, e)
            return 0

    async def acquire_export_slot(
        self,
        project_id: str,
    ) -> tuple[bool, str | None]:
        """
        Acquire an export slot for a project.

        Args:
            project_id: The project ID.

        Returns:
            Tuple of (acquired, job_id). Job ID is None if not acquired.
        """
        key = build_export_slot_key(project_id)
        limit = self._config.max_concurrent_exports_per_project
        ttl = self._config.export_lock_ttl_seconds

        try:
            # Check current count
            current_count = cast(int, await self._client.scard(key))  # type: ignore[misc]
            if current_count >= limit:
                logger.debug(
                    "Export slot denied for project %s: %d/%d active",
                    project_id,
                    current_count,
                    limit,
                )
                return False, None

            # Generate unique job ID
            job_id = str(uuid.uuid4())

            # Add to set
            await self._client.sadd(key, job_id)  # type: ignore[misc]
            await self._client.expire(key, ttl)

            logger.debug(
                "Export slot acquired for project %s: job %s",
                project_id,
                job_id,
            )
            return True, job_id
        except Exception as e:
            logger.error("Error acquiring export slot for %s: %s", project_id, e)
            return False, None

    async def release_export_slot(
        self,
        project_id: str,
        job_id: str,
    ) -> bool:
        """
        Release an export slot.

        Args:
            project_id: The project ID.
            job_id: The job ID to release.

        Returns:
            True if released, False otherwise.
        """
        key = build_export_slot_key(project_id)
        try:
            result = cast(int, await self._client.srem(key, job_id))  # type: ignore[misc]
            released = result > 0
            if released:
                logger.debug(
                    "Export slot released for project %s: job %s",
                    project_id,
                    job_id,
                )
            return released
        except Exception as e:
            logger.error("Error releasing export slot for %s: %s", project_id, e)
            return False

    async def get_active_exports(self, project_id: str) -> int:
        """Get count of active exports for a project."""
        key = build_export_slot_key(project_id)
        try:
            count = cast(int, await self._client.scard(key))  # type: ignore[misc]
            return count
        except Exception as e:
            logger.error("Error getting active exports for %s: %s", project_id, e)
            return 0

    async def acquire_cc_ingestion_slot(self) -> tuple[bool, str | None]:
        """
        Acquire the global CC ingestion slot.

        Only one CC ingestion can run at a time globally.

        Returns:
            Tuple of (acquired, job_id). Job ID is None if not acquired.
        """
        key = build_cc_ingestion_key()
        ttl = self._config.cc_ingestion_lock_ttl_seconds

        try:
            job_id = str(uuid.uuid4())

            # Use SET NX for atomic acquisition
            result = await self._client.set(
                key,
                job_id,
                nx=True,
                ex=ttl,
            )

            if result:
                logger.debug("CC ingestion slot acquired: job %s", job_id)
                return True, job_id
            else:
                logger.debug("CC ingestion slot denied: already active")
                return False, None
        except Exception as e:
            logger.error("Error acquiring CC ingestion slot: %s", e)
            return False, None

    async def release_cc_ingestion_slot(self, job_id: str) -> bool:
        """
        Release the global CC ingestion slot.

        Args:
            job_id: The job ID to release.

        Returns:
            True if released, False otherwise.
        """
        key = build_cc_ingestion_key()
        try:
            # Check if we own the lock
            current_job = await self._client.get(key)
            if current_job is None or current_job != job_id:
                logger.warning(
                    "CC ingestion release denied: owned by %s, not %s",
                    current_job,
                    job_id,
                )
                return False

            result = await self._client.delete(key)
            released = result > 0
            if released:
                logger.debug("CC ingestion slot released: job %s", job_id)
            return released
        except Exception as e:
            logger.error("Error releasing CC ingestion slot: %s", e)
            return False

    async def is_cc_ingestion_active(self) -> bool:
        """Check if a CC ingestion is currently active."""
        key = build_cc_ingestion_key()
        try:
            result = await self._client.exists(key)
            return result > 0
        except Exception as e:
            logger.error("Error checking CC ingestion status: %s", e)
            return False

    async def close(self) -> None:
        """Close the Redis connection."""
        await self._client.close()
