"""
Job scheduler using Redis sorted sets.

Provides scheduling capabilities for sync jobs including:
- Daily sync scheduling at configurable hour
- Backfill scheduling with date ranges
- Manual sync (immediate execution)
- Job status tracking and retry management
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis
from semrush_core.models.sync_run import SyncMode

from semrush_workers.config import get_worker_config

if TYPE_CHECKING:
    pass


class Scheduler:
    """
    Job scheduler using Redis sorted sets for time-based scheduling.

    Uses three main Redis structures:
    - Sorted set for scheduled jobs (score = execution timestamp)
    - Sorted set for processing jobs (score = started timestamp)
    - Hash/string keys for job data

    Attributes:
        SCHEDULED_JOBS_KEY: Redis key for scheduled jobs sorted set.
        PROCESSING_JOBS_KEY: Redis key for processing jobs sorted set.
        JOB_DATA_PREFIX: Redis key prefix for job data.
    """

    SCHEDULED_JOBS_KEY = "openahrush:jobs:scheduled"
    PROCESSING_JOBS_KEY = "openahrush:jobs:processing"
    JOB_DATA_PREFIX = "openahrush:job:"
    MAPPING_JOBS_PREFIX = "openahrush:mapping_jobs:"

    def __init__(self, redis: Redis) -> None:
        """
        Initialize the scheduler.

        Args:
            redis: Redis client for job storage.
        """
        self._redis = redis
        self._config = get_worker_config()

    async def schedule_daily_sync(
        self,
        mapping_id: uuid.UUID,
    ) -> str:
        """
        Schedule a daily sync job for the next sync window.

        The job is scheduled for the configured daily sync hour (default 2am UTC).

        Args:
            mapping_id: UUID of the integration mapping.

        Returns:
            Job ID of the scheduled job.
        """
        # Calculate next sync time
        now = datetime.now(UTC)
        next_sync = now.replace(
            hour=self._config.daily_sync_hour_utc,
            minute=0,
            second=0,
            microsecond=0,
        )

        # If we've passed today's sync time, schedule for tomorrow
        if next_sync <= now:
            next_sync += timedelta(days=1)

        return await self.schedule_at(
            mapping_id=mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
            execute_at=next_sync,
        )

    async def schedule_backfill(
        self,
        mapping_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> str:
        """
        Schedule a backfill sync job.

        Backfill jobs are scheduled for immediate execution.

        Args:
            mapping_id: UUID of the integration mapping.
            start_date: Start date for backfill range.
            end_date: End date for backfill range.

        Returns:
            Job ID of the scheduled job.
        """
        return await self.schedule_at(
            mapping_id=mapping_id,
            sync_mode=SyncMode.BACKFILL,
            execute_at=datetime.now(UTC),
            date_range_start=start_date,
            date_range_end=end_date,
        )

    async def schedule_manual_sync(
        self,
        mapping_id: uuid.UUID,
    ) -> str:
        """
        Schedule a manual sync job for immediate execution.

        Args:
            mapping_id: UUID of the integration mapping.

        Returns:
            Job ID of the scheduled job.
        """
        return await self.schedule_at(
            mapping_id=mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
            execute_at=datetime.now(UTC),
        )

    async def schedule_at(
        self,
        mapping_id: uuid.UUID,
        sync_mode: SyncMode,
        execute_at: datetime,
        date_range_start: date | None = None,
        date_range_end: date | None = None,
    ) -> str:
        """
        Schedule a sync job at a specific time.

        Args:
            mapping_id: UUID of the integration mapping.
            sync_mode: Sync mode (incremental or backfill).
            execute_at: When to execute the job.
            date_range_start: Optional start date for sync range.
            date_range_end: Optional end date for sync range.

        Returns:
            Job ID of the scheduled job.
        """
        job_id = str(uuid.uuid4())

        job_data = {
            "job_id": job_id,
            "mapping_id": str(mapping_id),
            "sync_mode": sync_mode.value,
            "status": "pending",
            "attempts": 0,
            "max_retries": self._config.max_retries,
            "date_range_start": date_range_start.isoformat() if date_range_start else None,
            "date_range_end": date_range_end.isoformat() if date_range_end else None,
            "created_at": datetime.now(UTC).isoformat(),
            "scheduled_at": execute_at.isoformat(),
        }

        # Store job data
        job_key = f"{self.JOB_DATA_PREFIX}{job_id}"
        await self._redis.set(job_key, json.dumps(job_data))

        # Add to scheduled jobs sorted set (score = execution timestamp)
        score = execute_at.timestamp()
        await self._redis.zadd(self.SCHEDULED_JOBS_KEY, {job_id: score})

        # Track job by mapping ID for easy lookup
        mapping_key = f"{self.MAPPING_JOBS_PREFIX}{mapping_id}"
        await self._redis.sadd(mapping_key, job_id)

        return job_id

    async def get_job_data(self, job_id: str) -> dict[str, Any] | None:
        """
        Get job data by ID.

        Args:
            job_id: Job ID to retrieve.

        Returns:
            Job data dictionary or None if not found.
        """
        job_key = f"{self.JOB_DATA_PREFIX}{job_id}"
        data = await self._redis.get(job_key)

        if data is None:
            return None

        return json.loads(data)

    async def get_pending_jobs(self) -> list[dict[str, Any]]:
        """
        Get all pending scheduled jobs.

        Returns:
            List of job data dictionaries.
        """
        job_ids = await self._redis.zrange(self.SCHEDULED_JOBS_KEY, 0, -1)

        jobs = []
        for job_id in job_ids:
            job_data = await self.get_job_data(job_id)
            if job_data:
                jobs.append(job_data)

        return jobs

    async def get_due_jobs(self) -> list[dict[str, Any]]:
        """
        Get jobs that are due for execution.

        Returns:
            List of job data dictionaries for jobs ready to run.
        """
        now = datetime.now(UTC).timestamp()

        # Get all jobs with score <= now
        job_ids = await self._redis.zrangebyscore(
            self.SCHEDULED_JOBS_KEY,
            "-inf",
            now,
        )

        jobs = []
        for job_id in job_ids:
            job_data = await self.get_job_data(job_id)
            if job_data:
                jobs.append(job_data)

        return jobs

    async def process_due_jobs(self) -> list[dict[str, Any]]:
        """
        Move due jobs from scheduled to processing queue.

        Returns:
            List of job data dictionaries that were moved.
        """
        now = datetime.now(UTC)
        now_ts = now.timestamp()

        # Get due jobs
        job_ids = await self._redis.zrangebyscore(
            self.SCHEDULED_JOBS_KEY,
            "-inf",
            now_ts,
        )

        processed = []

        for job_id in job_ids:
            # Atomically move from scheduled to processing
            removed = await self._redis.zrem(self.SCHEDULED_JOBS_KEY, job_id)

            if removed:
                # Add to processing queue
                await self._redis.zadd(
                    self.PROCESSING_JOBS_KEY,
                    {job_id: now_ts},
                )

                # Update job status
                job_data = await self.get_job_data(job_id)
                if job_data:
                    job_data["status"] = "processing"
                    job_data["started_at"] = now.isoformat()

                    job_key = f"{self.JOB_DATA_PREFIX}{job_id}"
                    await self._redis.set(job_key, json.dumps(job_data))

                    processed.append(job_data)

        return processed

    async def mark_job_completed(
        self,
        job_id: str,
        records_written: int = 0,
    ) -> None:
        """
        Mark a job as completed.

        Args:
            job_id: Job ID to mark completed.
            records_written: Number of records written during sync.
        """
        now = datetime.now(UTC)

        # Remove from processing queue
        await self._redis.zrem(self.PROCESSING_JOBS_KEY, job_id)

        # Update job data
        job_data = await self.get_job_data(job_id)
        if job_data:
            job_data["status"] = "completed"
            job_data["completed_at"] = now.isoformat()
            job_data["records_written"] = records_written

            job_key = f"{self.JOB_DATA_PREFIX}{job_id}"
            await self._redis.set(
                job_key,
                json.dumps(job_data),
                ex=self._config.job_data_ttl_seconds,
            )

    async def mark_job_failed(
        self,
        job_id: str,
        error: str,
    ) -> None:
        """
        Mark a job as failed.

        Args:
            job_id: Job ID to mark failed.
            error: Error message.
        """
        now = datetime.now(UTC)

        # Remove from processing queue
        await self._redis.zrem(self.PROCESSING_JOBS_KEY, job_id)

        # Update job data
        job_data = await self.get_job_data(job_id)
        if job_data:
            job_data["status"] = "failed"
            job_data["completed_at"] = now.isoformat()
            job_data["error"] = error

            job_key = f"{self.JOB_DATA_PREFIX}{job_id}"
            await self._redis.set(job_key, json.dumps(job_data))

    async def retry_job(self, job_id: str) -> bool:
        """
        Retry a failed job with exponential backoff.

        Args:
            job_id: Job ID to retry.

        Returns:
            True if retry was scheduled, False if max retries exceeded.
        """
        job_data = await self.get_job_data(job_id)
        if not job_data:
            return False

        attempts = job_data.get("attempts", 0) + 1
        max_retries = job_data.get("max_retries", self._config.max_retries)

        if attempts > max_retries:
            return False

        # Calculate backoff delay
        base_delay = self._config.base_backoff_seconds
        delay = base_delay * (2 ** (attempts - 1))

        # Schedule retry
        retry_at = datetime.now(UTC) + timedelta(seconds=delay)

        # Update job data
        job_data["status"] = "pending"
        job_data["attempts"] = attempts
        job_data["scheduled_at"] = retry_at.isoformat()

        job_key = f"{self.JOB_DATA_PREFIX}{job_id}"
        await self._redis.set(job_key, json.dumps(job_data))

        # Add back to scheduled queue
        await self._redis.zadd(
            self.SCHEDULED_JOBS_KEY,
            {job_id: retry_at.timestamp()},
        )

        return True

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a scheduled job.

        Args:
            job_id: Job ID to cancel.

        Returns:
            True if job was cancelled, False if not found.
        """
        # Remove from scheduled queue
        removed = await self._redis.zrem(self.SCHEDULED_JOBS_KEY, job_id)

        if removed:
            # Update job data
            job_data = await self.get_job_data(job_id)
            if job_data:
                job_data["status"] = "cancelled"
                job_data["cancelled_at"] = datetime.now(UTC).isoformat()

                job_key = f"{self.JOB_DATA_PREFIX}{job_id}"
                await self._redis.set(
                    job_key,
                    json.dumps(job_data),
                    ex=self._config.job_data_ttl_seconds,
                )

            return True

        return False

    async def get_jobs_for_mapping(
        self,
        mapping_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """
        Get all jobs for a specific mapping.

        Args:
            mapping_id: UUID of the integration mapping.

        Returns:
            List of job data dictionaries.
        """
        mapping_key = f"{self.MAPPING_JOBS_PREFIX}{mapping_id}"
        job_ids = await self._redis.smembers(mapping_key)

        jobs = []
        for job_id in job_ids:
            job_data = await self.get_job_data(job_id)
            if job_data:
                jobs.append(job_data)

        return jobs
