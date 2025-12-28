"""
Worker for processing sync jobs from the queue.

Provides:
- Main processing loop with configurable polling
- Concurrent job execution with semaphore limiting
- Graceful shutdown handling
- Job timeout management
- Retry scheduling for failed jobs
"""

from __future__ import annotations

import asyncio
import logging
import signal
import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis

from semrush_core.models.sync_run import SyncMode
from semrush_workers.config import WorkerConfig, get_worker_config
from semrush_workers.jobs.property_sync_job import PropertySyncJob
from semrush_workers.jobs.sync_job import SyncJob
from semrush_workers.scheduler import Scheduler

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from semrush_workers.jobs.base import Job

logger = logging.getLogger(__name__)


class Worker:
    """
    Background worker for processing sync jobs.

    Polls the job queue and processes jobs with configurable
    concurrency limits and timeouts.

    Attributes:
        max_concurrent_jobs: Maximum jobs to process concurrently.
        job_timeout: Maximum time for a single job in seconds.
    """

    def __init__(
        self,
        redis: Redis,
        max_concurrent_jobs: int | None = None,
        poll_interval: float | None = None,
        job_timeout: int | None = None,
        config: WorkerConfig | None = None,
    ) -> None:
        """
        Initialize the worker.

        Args:
            redis: Redis client for job queue.
            max_concurrent_jobs: Override max concurrent jobs.
            poll_interval: Override poll interval.
            job_timeout: Override job timeout.
            config: Worker configuration override.
        """
        self._config = config or get_worker_config()
        self._redis = redis
        self._scheduler = Scheduler(redis)

        self.max_concurrent_jobs = max_concurrent_jobs or self._config.max_concurrent_jobs
        self.poll_interval = poll_interval or self._config.poll_interval
        self.job_timeout = job_timeout or self._config.job_timeout

        self._running = False
        self._shutdown_event = asyncio.Event()
        self._semaphore = asyncio.Semaphore(self.max_concurrent_jobs)
        self._active_tasks: set[asyncio.Task[Any]] = set()

    async def run(self) -> None:
        """
        Start the worker main loop.

        Polls for due jobs and processes them with concurrency limits.
        Handles graceful shutdown on SIGINT/SIGTERM.
        """
        self._running = True
        self._setup_signal_handlers()

        logger.info(
            "Starting worker with max_concurrent=%d, poll_interval=%.1f, timeout=%d",
            self.max_concurrent_jobs,
            self.poll_interval,
            self.job_timeout,
        )

        try:
            while self._running:
                try:
                    # Process due jobs
                    processed_jobs = await self._scheduler.process_due_jobs()

                    for job_data in processed_jobs:
                        # Acquire semaphore to limit concurrency
                        async with self._semaphore:
                            task = asyncio.create_task(
                                self._execute_job(job_data)
                            )
                            self._active_tasks.add(task)
                            task.add_done_callback(self._active_tasks.discard)

                    # Wait for poll interval or shutdown
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=self.poll_interval,
                        )
                        # Shutdown requested
                        break
                    except asyncio.TimeoutError:
                        # Normal timeout, continue polling
                        pass

                except Exception as e:
                    logger.exception("Error in worker loop: %s", e)
                    await asyncio.sleep(self.poll_interval)

        except asyncio.CancelledError:
            logger.info("Worker cancelled")
        finally:
            # Wait for active tasks to complete
            if self._active_tasks:
                logger.info("Waiting for %d active tasks to complete", len(self._active_tasks))
                await asyncio.gather(*self._active_tasks, return_exceptions=True)

            self._running = False
            logger.info("Worker stopped")

    async def stop(self) -> None:
        """Request graceful shutdown of the worker."""
        logger.info("Shutdown requested")
        self._running = False
        self._shutdown_event.set()

    async def _execute_job(self, job_data: dict[str, Any]) -> None:
        """
        Execute a single job with timeout handling.

        Args:
            job_data: Job data dictionary from scheduler.
        """
        job_id = job_data["job_id"]
        logger.info("Executing job %s", job_id)

        try:
            # Create job instance from data
            job = self._create_job_from_data(job_data)

            # Get dependencies (would be injected in production)
            from semrush_core.database import get_session_context

            async with get_session_context() as db_session:
                # Execute with timeout
                try:
                    result = await asyncio.wait_for(
                        self._run_job(job, db_session),
                        timeout=self.job_timeout,
                    )
                except asyncio.TimeoutError:
                    result = {
                        "success": False,
                        "error": f"Job timed out after {self.job_timeout} seconds",
                    }

            if result.get("success"):
                await self._scheduler.mark_job_completed(
                    job_id=job_id,
                    records_written=result.get("records_written", 0),
                )
                logger.info("Job %s completed successfully", job_id)
            else:
                error = result.get("error", "Unknown error")
                await self._scheduler.mark_job_failed(job_id, error)

                # Attempt retry
                if await self._scheduler.retry_job(job_id):
                    logger.info("Job %s scheduled for retry", job_id)
                else:
                    logger.error("Job %s failed permanently: %s", job_id, error)

        except Exception as e:
            logger.exception("Error executing job %s: %s", job_id, e)
            await self._scheduler.mark_job_failed(job_id, str(e))

    async def _run_job(
        self,
        job: "Job",
        db_session: "AsyncSession",
    ) -> dict[str, Any]:
        """
        Run a job with its dependencies.

        Args:
            job: Job instance to execute.
            db_session: Database session.

        Returns:
            Result dictionary from job execution.
        """
        # This would inject actual services in production
        if isinstance(job, SyncJob):
            # For now, return a placeholder - actual service would be injected
            return await job.execute(db_session=db_session)
        elif isinstance(job, PropertySyncJob):
            return await job.execute(db_session=db_session)
        else:
            raise ValueError(f"Unknown job type: {type(job)}")

    def _create_job_from_data(self, job_data: dict[str, Any]) -> "Job":
        """
        Create a job instance from scheduler data.

        Args:
            job_data: Job data dictionary.

        Returns:
            Job instance.
        """
        sync_mode_str = job_data.get("sync_mode", "incremental")
        sync_mode = SyncMode(sync_mode_str)

        return SyncJob.create(
            mapping_id=uuid.UUID(job_data["mapping_id"]),
            sync_mode=sync_mode,
            date_range_start=(
                date.fromisoformat(job_data["date_range_start"])
                if job_data.get("date_range_start")
                else None
            ),
            date_range_end=(
                date.fromisoformat(job_data["date_range_end"])
                if job_data.get("date_range_end")
                else None
            ),
        )

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        try:
            loop = asyncio.get_running_loop()

            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(self.stop()),
                )
        except NotImplementedError:
            # Windows doesn't support signal handlers in async loops
            pass

    async def process_job(
        self,
        job: "Job",
        db_session: "AsyncSession",
        data_sync_service: Any | None = None,
        discovery_service: Any | None = None,
    ) -> dict[str, Any]:
        """
        Process a single job directly (for testing).

        Args:
            job: Job instance to execute.
            db_session: Database session.
            data_sync_service: Optional data sync service.
            discovery_service: Optional discovery service.

        Returns:
            Result dictionary from job execution.
        """
        # Note: job.execute() handles record_attempt() internally

        try:
            if isinstance(job, SyncJob):
                result = await asyncio.wait_for(
                    job.execute(
                        db_session=db_session,
                        data_sync_service=data_sync_service,
                    ),
                    timeout=self.job_timeout,
                )
            elif isinstance(job, PropertySyncJob):
                result = await asyncio.wait_for(
                    job.execute(
                        db_session=db_session,
                        discovery_service=discovery_service,
                    ),
                    timeout=self.job_timeout,
                )
            else:
                result = {"success": False, "error": f"Unknown job type: {type(job)}"}

        except asyncio.TimeoutError:
            result = {
                "success": False,
                "error": f"Job timed out after {self.job_timeout} seconds",
            }

        return result


async def run_worker() -> None:
    """Entry point for running the worker."""
    import redis.asyncio as redis

    config = get_worker_config()

    async with redis.from_url(config.redis_url) as redis_client:
        worker = Worker(redis=redis_client, config=config)
        await worker.run()


def main() -> None:
    """CLI entry point for the worker."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
