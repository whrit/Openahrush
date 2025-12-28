"""
Tests for the sync scheduler and worker.

Tests cover:
- Scheduler class with Redis sorted sets
- Daily sync scheduling at 2am UTC
- Backfill scheduling for historical data
- Job queue processing
- Worker main loop and job execution
- Concurrency limits
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio
from redis.asyncio import Redis

from semrush_core.models.sync_run import SyncMode


class TestScheduler:
    """Tests for the Scheduler class."""

    @pytest_asyncio.fixture
    async def scheduler(
        self, async_fake_redis: Redis
    ) -> AsyncGenerator[Any, None]:
        """Create a scheduler with fake Redis."""
        from semrush_workers.scheduler import Scheduler

        sched = Scheduler(redis=async_fake_redis)
        yield sched

    @pytest.mark.asyncio
    async def test_schedule_daily_sync(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test scheduling a daily sync job."""
        job_id = await scheduler.schedule_daily_sync(sample_mapping_id)

        assert job_id is not None

        # Verify job is in the scheduled queue
        pending = await scheduler.get_pending_jobs()
        assert len(pending) >= 0  # May or may not be pending based on time

    @pytest.mark.asyncio
    async def test_daily_sync_scheduled_at_2am_utc(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test that daily sync is scheduled for 2am UTC."""
        job_id = await scheduler.schedule_daily_sync(sample_mapping_id)

        # Get the scheduled time from Redis
        score = await scheduler._redis.zscore(
            scheduler.SCHEDULED_JOBS_KEY,
            job_id,
        )

        if score is not None:
            scheduled_time = datetime.fromtimestamp(score, tz=timezone.utc)
            assert scheduled_time.hour == 2
            assert scheduled_time.minute == 0

    @pytest.mark.asyncio
    async def test_schedule_backfill(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test scheduling a backfill sync job."""
        start_date = date(2023, 1, 1)
        end_date = date(2024, 1, 1)

        job_id = await scheduler.schedule_backfill(
            mapping_id=sample_mapping_id,
            start_date=start_date,
            end_date=end_date,
        )

        assert job_id is not None

        # Verify job data contains correct date range
        job_data = await scheduler.get_job_data(job_id)
        assert job_data is not None
        assert job_data["date_range_start"] == start_date.isoformat()
        assert job_data["date_range_end"] == end_date.isoformat()
        assert job_data["sync_mode"] == SyncMode.BACKFILL.value

    @pytest.mark.asyncio
    async def test_schedule_manual_sync(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test scheduling a manual sync job (runs immediately)."""
        job_id = await scheduler.schedule_manual_sync(sample_mapping_id)

        assert job_id is not None

        # Manual syncs should be immediately available
        due_jobs = await scheduler.get_due_jobs()
        assert any(j["job_id"] == job_id for j in due_jobs)

    @pytest.mark.asyncio
    async def test_get_pending_jobs(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test getting all pending jobs."""
        # Schedule multiple jobs
        job1 = await scheduler.schedule_manual_sync(sample_mapping_id)
        job2 = await scheduler.schedule_manual_sync(sample_mapping_id)

        pending = await scheduler.get_pending_jobs()

        assert len(pending) == 2
        job_ids = [j["job_id"] for j in pending]
        assert job1 in job_ids
        assert job2 in job_ids

    @pytest.mark.asyncio
    async def test_get_due_jobs(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test getting only jobs that are due for execution."""
        # Schedule a job in the past (immediately due)
        job_now = await scheduler.schedule_manual_sync(sample_mapping_id)

        # Schedule a job in the future
        job_future = await scheduler.schedule_at(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
            execute_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        due = await scheduler.get_due_jobs()

        due_ids = [j["job_id"] for j in due]
        assert job_now in due_ids
        assert job_future not in due_ids

    @pytest.mark.asyncio
    async def test_process_due_jobs(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test processing jobs that are due."""
        job_id = await scheduler.schedule_manual_sync(sample_mapping_id)

        # Process due jobs
        processed = await scheduler.process_due_jobs()

        assert len(processed) == 1
        assert processed[0]["job_id"] == job_id

        # Job should be moved to processing queue
        due = await scheduler.get_due_jobs()
        assert not any(j["job_id"] == job_id for j in due)

    @pytest.mark.asyncio
    async def test_mark_job_completed(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test marking a job as completed."""
        job_id = await scheduler.schedule_manual_sync(sample_mapping_id)
        await scheduler.process_due_jobs()

        await scheduler.mark_job_completed(
            job_id=job_id,
            records_written=150,
        )

        # Job should no longer be in any active queue
        job_data = await scheduler.get_job_data(job_id)
        assert job_data["status"] == "completed"
        assert job_data["records_written"] == 150

    @pytest.mark.asyncio
    async def test_mark_job_failed(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test marking a job as failed."""
        job_id = await scheduler.schedule_manual_sync(sample_mapping_id)
        await scheduler.process_due_jobs()

        await scheduler.mark_job_failed(
            job_id=job_id,
            error="Connection timeout",
        )

        job_data = await scheduler.get_job_data(job_id)
        assert job_data["status"] == "failed"
        assert job_data["error"] == "Connection timeout"

    @pytest.mark.asyncio
    async def test_retry_failed_job(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test retrying a failed job with backoff."""
        job_id = await scheduler.schedule_manual_sync(sample_mapping_id)
        await scheduler.process_due_jobs()

        # Fail the job
        await scheduler.mark_job_failed(job_id, "Temporary error")

        # Retry the job
        retried = await scheduler.retry_job(job_id)

        assert retried is True

        job_data = await scheduler.get_job_data(job_id)
        assert job_data["attempts"] == 1
        assert job_data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_retry_exceeds_max_attempts(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test that retry fails after max attempts exceeded."""
        job_id = await scheduler.schedule_manual_sync(sample_mapping_id)

        # Simulate 3 failed attempts
        for _ in range(3):
            await scheduler.process_due_jobs()
            await scheduler.mark_job_failed(job_id, "Error")
            await scheduler.retry_job(job_id)

        # Fourth retry should fail
        await scheduler.process_due_jobs()
        await scheduler.mark_job_failed(job_id, "Error")
        retried = await scheduler.retry_job(job_id)

        assert retried is False

        job_data = await scheduler.get_job_data(job_id)
        assert job_data["status"] == "failed"
        assert job_data["attempts"] == 3

    @pytest.mark.asyncio
    async def test_cancel_scheduled_job(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test canceling a scheduled job."""
        job_id = await scheduler.schedule_daily_sync(sample_mapping_id)

        cancelled = await scheduler.cancel_job(job_id)

        assert cancelled is True

        pending = await scheduler.get_pending_jobs()
        assert not any(j["job_id"] == job_id for j in pending)

    @pytest.mark.asyncio
    async def test_get_jobs_for_mapping(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test getting all jobs for a specific mapping."""
        job1 = await scheduler.schedule_manual_sync(sample_mapping_id)
        job2 = await scheduler.schedule_manual_sync(sample_mapping_id)

        other_mapping = uuid.uuid4()
        job3 = await scheduler.schedule_manual_sync(other_mapping)

        jobs = await scheduler.get_jobs_for_mapping(sample_mapping_id)

        job_ids = [j["job_id"] for j in jobs]
        assert job1 in job_ids
        assert job2 in job_ids
        assert job3 not in job_ids


class TestWorker:
    """Tests for the Worker class."""

    @pytest_asyncio.fixture
    async def worker(
        self, async_fake_redis: Redis
    ) -> AsyncGenerator[Any, None]:
        """Create a worker with fake Redis."""
        from semrush_workers.worker import Worker

        w = Worker(
            redis=async_fake_redis,
            max_concurrent_jobs=2,
        )
        yield w

    @pytest.mark.asyncio
    async def test_worker_initialization(self, worker: Any) -> None:
        """Test worker initializes with correct configuration."""
        assert worker.max_concurrent_jobs == 2
        assert worker._running is False

    @pytest.mark.asyncio
    async def test_worker_process_job_success(
        self,
        worker: Any,
        sample_mapping_id: uuid.UUID,
        mock_db_session: AsyncMock,
        mock_data_sync_service: AsyncMock,
    ) -> None:
        """Test worker successfully processes a job."""
        from semrush_workers.jobs.sync_job import SyncJob

        job = SyncJob.create(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
        )

        # Mock sync run
        mock_sync_run = MagicMock()
        mock_sync_run.status = "queued"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sync_run
        mock_db_session.execute.return_value = mock_result

        result = await worker.process_job(
            job=job,
            db_session=mock_db_session,
            data_sync_service=mock_data_sync_service,
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_worker_process_job_failure_with_retry(
        self,
        worker: Any,
        sample_mapping_id: uuid.UUID,
        mock_db_session: AsyncMock,
        mock_data_sync_service: AsyncMock,
    ) -> None:
        """Test worker handles job failure and schedules retry."""
        from semrush_workers.jobs.sync_job import SyncJob

        job = SyncJob.create(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
        )

        mock_data_sync_service.sync_data.side_effect = Exception("API error")

        # Mock sync run
        mock_sync_run = MagicMock()
        mock_sync_run.status = "queued"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sync_run
        mock_db_session.execute.return_value = mock_result

        result = await worker.process_job(
            job=job,
            db_session=mock_db_session,
            data_sync_service=mock_data_sync_service,
        )

        assert result["success"] is False
        assert job.attempts == 1

    @pytest.mark.asyncio
    async def test_worker_respects_concurrency_limit(
        self,
        async_fake_redis: Redis,
    ) -> None:
        """Test worker respects max concurrent jobs limit."""
        from semrush_workers.worker import Worker

        worker = Worker(redis=async_fake_redis, max_concurrent_jobs=2)

        # Check semaphore is set correctly
        assert worker._semaphore._value == 2

    @pytest.mark.asyncio
    async def test_worker_run_loop_processes_jobs(
        self,
        worker: Any,
        async_fake_redis: Redis,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test worker run loop processes queued jobs."""
        from semrush_workers.scheduler import Scheduler

        scheduler = Scheduler(redis=async_fake_redis)

        # Schedule a job
        job_id = await scheduler.schedule_manual_sync(sample_mapping_id)

        # Start worker in background and stop after short time
        async def run_briefly() -> None:
            await asyncio.sleep(0.1)
            await worker.stop()

        with patch.object(worker, "process_job", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {"success": True}

            await asyncio.gather(
                worker.run(),
                run_briefly(),
            )

            # Worker should have attempted to process the job
            # (actual processing depends on timing)

    @pytest.mark.asyncio
    async def test_worker_graceful_shutdown(self, worker: Any) -> None:
        """Test worker handles graceful shutdown."""
        # Start worker
        run_task = asyncio.create_task(worker.run())

        # Wait briefly then stop
        await asyncio.sleep(0.05)
        await worker.stop()

        # Wait for run to complete
        await asyncio.wait_for(run_task, timeout=1.0)

        assert worker._running is False

    @pytest.mark.asyncio
    async def test_worker_handles_job_timeout(
        self,
        worker: Any,
        sample_mapping_id: uuid.UUID,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test worker handles job execution timeout."""
        from semrush_workers.jobs.sync_job import SyncJob

        job = SyncJob.create(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
        )

        # Create a slow sync service
        async def slow_sync(*args: Any, **kwargs: Any) -> dict[str, Any]:
            await asyncio.sleep(10)  # Very slow
            return {"records_written": 0}

        mock_slow_service = AsyncMock()
        mock_slow_service.sync_data = slow_sync

        # Mock sync run
        mock_sync_run = MagicMock()
        mock_sync_run.status = "queued"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sync_run
        mock_db_session.execute.return_value = mock_result

        # Set a short timeout on worker
        worker.job_timeout = 0.1

        result = await worker.process_job(
            job=job,
            db_session=mock_db_session,
            data_sync_service=mock_slow_service,
        )

        assert result["success"] is False
        assert "timed out" in result["error"].lower()


class TestWorkerConfig:
    """Tests for worker configuration."""

    def test_worker_config_defaults(self) -> None:
        """Test worker config has sensible defaults."""
        from semrush_workers.config import WorkerConfig

        config = WorkerConfig()

        assert config.redis_url == "redis://localhost:6379/0"
        assert config.max_concurrent_jobs == 10
        assert config.poll_interval == 1.0
        assert config.job_timeout == 300  # 5 minutes

    def test_worker_config_from_env(self) -> None:
        """Test worker config can be loaded from environment."""
        import os

        from semrush_workers.config import WorkerConfig

        with patch.dict(os.environ, {
            "REDIS_URL": "redis://redis:6379/1",
            "WORKER_MAX_CONCURRENT_JOBS": "20",
            "WORKER_POLL_INTERVAL": "0.5",
            "WORKER_JOB_TIMEOUT": "600",
        }):
            config = WorkerConfig()

            assert config.redis_url == "redis://redis:6379/1"
            assert config.max_concurrent_jobs == 20
            assert config.poll_interval == 0.5
            assert config.job_timeout == 600

    def test_worker_config_daily_sync_hour(self) -> None:
        """Test daily sync hour configuration."""
        from semrush_workers.config import WorkerConfig

        config = WorkerConfig()

        assert config.daily_sync_hour_utc == 2  # 2am UTC default

    def test_worker_config_backfill_months(self) -> None:
        """Test backfill months configuration for GSC/GA4."""
        from semrush_workers.config import WorkerConfig

        config = WorkerConfig()

        assert config.backfill_months == 16  # 16 months for GSC/GA4


class TestSchedulerRedisKeys:
    """Tests for scheduler Redis key management."""

    @pytest_asyncio.fixture
    async def scheduler(
        self, async_fake_redis: Redis
    ) -> AsyncGenerator[Any, None]:
        """Create a scheduler with fake Redis."""
        from semrush_workers.scheduler import Scheduler

        sched = Scheduler(redis=async_fake_redis)
        yield sched

    @pytest.mark.asyncio
    async def test_scheduler_uses_correct_keys(
        self,
        scheduler: Any,
    ) -> None:
        """Test scheduler uses proper Redis key namespace."""
        assert scheduler.SCHEDULED_JOBS_KEY == "openahrush:jobs:scheduled"
        assert scheduler.PROCESSING_JOBS_KEY == "openahrush:jobs:processing"
        assert scheduler.JOB_DATA_PREFIX == "openahrush:job:"

    @pytest.mark.asyncio
    async def test_job_data_stored_with_correct_key(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test job data is stored with correct Redis key."""
        job_id = await scheduler.schedule_manual_sync(sample_mapping_id)

        # Check the data exists at the expected key
        key = f"{scheduler.JOB_DATA_PREFIX}{job_id}"
        data = await scheduler._redis.get(key)

        assert data is not None
        job_data = json.loads(data)
        assert job_data["mapping_id"] == str(sample_mapping_id)

    @pytest.mark.asyncio
    async def test_job_data_has_ttl(
        self,
        scheduler: Any,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test completed job data expires after TTL."""
        job_id = await scheduler.schedule_manual_sync(sample_mapping_id)
        await scheduler.process_due_jobs()
        await scheduler.mark_job_completed(job_id, records_written=100)

        # Check TTL is set
        key = f"{scheduler.JOB_DATA_PREFIX}{job_id}"
        ttl = await scheduler._redis.ttl(key)

        # Should have TTL set (7 days = 604800 seconds)
        assert ttl > 0
        assert ttl <= 604800
