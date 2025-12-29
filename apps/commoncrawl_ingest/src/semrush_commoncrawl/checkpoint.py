"""
Ingestion checkpoint for resumable Common Crawl processing.

Provides Redis-based progress tracking and file completion markers
for resuming interrupted ingestion jobs.
"""

from __future__ import annotations

import json
from collections.abc import Set as AbstractSet
from typing import Any, Protocol


class RedisProtocol(Protocol):
    """Protocol for async Redis client."""

    async def get(self, key: str) -> str | None:
        """Get value by key."""
        ...

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Set value with optional expiration."""
        ...

    async def delete(self, *keys: str) -> int:
        """Delete keys."""
        ...

    async def sadd(self, key: str, *members: str) -> int:
        """Add members to set."""
        ...

    async def sismember(self, key: str, member: str) -> bool:
        """Check if member is in set."""
        ...

    async def smembers(self, key: str) -> AbstractSet[str]:
        """Get all members of set."""
        ...


class IngestionCheckpoint:
    """
    Redis-based checkpoint for resumable ingestion.

    Tracks processing progress and completed files to enable
    resuming interrupted ingestion jobs.

    Attributes:
        redis: Async Redis client.
        job_id: Unique identifier for the ingestion job.
        prefix: Redis key prefix for checkpoint data.
    """

    def __init__(
        self,
        redis: RedisProtocol,
        job_id: str,
        prefix: str = "commoncrawl:checkpoint",
    ) -> None:
        """
        Initialize the checkpoint.

        Args:
            redis: Async Redis client instance.
            job_id: Unique identifier for this ingestion job.
            prefix: Redis key prefix for organizing checkpoint data.
        """
        self.redis = redis
        self.job_id = job_id
        self.prefix = prefix

    def _progress_key(self) -> str:
        """Get Redis key for progress data."""
        return f"{self.prefix}:{self.job_id}:progress"

    def _completed_files_key(self) -> str:
        """Get Redis key for completed files set."""
        return f"{self.prefix}:{self.job_id}:completed"

    async def save_progress(
        self,
        files_processed: int,
        edges_ingested: int,
        current_file: str | None = None,
    ) -> None:
        """
        Save current progress to Redis.

        Args:
            files_processed: Number of files processed so far.
            edges_ingested: Number of edges ingested so far.
            current_file: Currently processing file path.
        """
        data: dict[str, int | str] = {
            "files_processed": files_processed,
            "edges_ingested": edges_ingested,
        }
        if current_file:
            data["current_file"] = current_file
        await self.redis.set(self._progress_key(), json.dumps(data))

    async def get_progress(self) -> dict[str, Any] | None:
        """
        Get current progress from Redis.

        Returns:
            Progress data dictionary or None if not found.
        """
        data = await self.redis.get(self._progress_key())
        if data is None:
            return None
        return json.loads(data)

    async def mark_file_complete(self, file_path: str) -> None:
        """
        Mark a file as completely processed.

        Args:
            file_path: Path of the completed file.
        """
        await self.redis.sadd(self._completed_files_key(), file_path)

    async def is_file_complete(self, file_path: str) -> bool:
        """
        Check if a file has been completely processed.

        Args:
            file_path: Path to check.

        Returns:
            True if the file is marked as complete.
        """
        return await self.redis.sismember(self._completed_files_key(), file_path)

    async def get_completed_files(self) -> AbstractSet[str]:
        """
        Get all completed file paths.

        Returns:
            Set of completed file paths.
        """
        return await self.redis.smembers(self._completed_files_key())

    async def clear(self) -> None:
        """Remove all checkpoint data for this job."""
        await self.redis.delete(self._progress_key(), self._completed_files_key())
