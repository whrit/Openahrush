"""
Worker runner and job processing.

Provides:
- Main worker loop
- Job registration and dispatch
- Graceful shutdown handling
- Retry logic with exponential backoff

Note: This is a placeholder implementation. Full Redis-based
worker with proper job processing will be implemented later.
"""

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class JobStatus(StrEnum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Job:
    """
    Represents a background job to be processed.

    Attributes:
        id: Unique job identifier.
        type: Job type (matches registered handler).
        payload: Job-specific data.
        status: Current execution status.
        attempts: Number of execution attempts.
        max_retries: Maximum retry attempts.
        created_at: When the job was created.
        started_at: When execution started.
        completed_at: When execution finished.
        error: Error message if failed.
    """

    id: str
    type: str
    payload: dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


# Type alias for job handlers
JobHandler = Callable[[Job], Awaitable[None]]


class WorkerRunner:
    """
    Background worker for processing jobs from a queue.

    Handles:
    - Job polling from Redis queue
    - Job dispatch to registered handlers
    - Retry logic with exponential backoff
    - Graceful shutdown on signals

    Example:
        runner = WorkerRunner()

        @runner.register("crawl.start")
        async def handle_crawl_start(job: Job) -> None:
            project_id = job.payload["project_id"]
            # Start crawl...

        await runner.run()
    """

    def __init__(
        self,
        *,
        poll_interval: float = 1.0,
        max_concurrent_jobs: int = 10,
    ) -> None:
        """
        Initialize the worker runner.

        Args:
            poll_interval: Seconds between queue polls.
            max_concurrent_jobs: Maximum jobs to process concurrently.
        """
        self.poll_interval = poll_interval
        self.max_concurrent_jobs = max_concurrent_jobs
        self._handlers: dict[str, JobHandler] = {}
        self._running = False
        self._shutdown_event = asyncio.Event()

    def register(self, job_type: str) -> Callable[[JobHandler], JobHandler]:
        """
        Register a job handler.

        Use as a decorator to register handlers for specific job types.

        Args:
            job_type: Type of job this handler processes.

        Returns:
            Decorator function.

        Example:
            @runner.register("integration.sync")
            async def handle_sync(job: Job) -> None:
                ...
        """

        def decorator(handler: JobHandler) -> JobHandler:
            self._handlers[job_type] = handler
            logger.info("Registered handler for job type: %s", job_type)
            return handler

        return decorator

    async def run(self) -> None:
        """
        Start the worker loop.

        Polls for jobs and dispatches them to registered handlers.
        Handles graceful shutdown on SIGINT/SIGTERM.
        """
        self._running = True
        self._setup_signal_handlers()

        logger.info(
            "Starting worker with %d registered handlers",
            len(self._handlers),
        )

        try:
            while self._running:
                # TODO: Poll jobs from Redis queue
                # For now, just wait for the poll interval
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.poll_interval,
                    )
                    # If we get here, shutdown was requested
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, continue polling
                    pass

        except asyncio.CancelledError:
            logger.info("Worker cancelled")
        finally:
            self._running = False
            logger.info("Worker stopped")

    async def stop(self) -> None:
        """Request graceful shutdown of the worker."""
        logger.info("Shutdown requested")
        self._running = False
        self._shutdown_event.set()

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

    async def _process_job(self, job: Job) -> None:
        """
        Process a single job.

        Dispatches to the registered handler and handles errors/retries.

        Args:
            job: Job to process.
        """
        handler = self._handlers.get(job.type)

        if handler is None:
            logger.error("No handler registered for job type: %s", job.type)
            job.status = JobStatus.FAILED
            job.error = f"No handler for job type: {job.type}"
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.attempts += 1

        try:
            await handler(job)
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            logger.info("Job %s completed successfully", job.id)

        except Exception as e:
            logger.exception("Job %s failed: %s", job.id, e)
            job.error = str(e)

            if job.attempts < job.max_retries:
                job.status = JobStatus.RETRYING
                # TODO: Re-queue with exponential backoff
            else:
                job.status = JobStatus.FAILED
                logger.error(
                    "Job %s failed after %d attempts",
                    job.id,
                    job.attempts,
                )


# Global runner instance
_runner: WorkerRunner | None = None


def get_runner() -> WorkerRunner:
    """Get or create the global worker runner instance."""
    global _runner
    if _runner is None:
        _runner = WorkerRunner()
    return _runner


def main() -> None:
    """Entry point for the worker CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    runner = get_runner()

    # Register example handlers (will be replaced with actual handlers)
    @runner.register("example.job")
    async def handle_example(job: Job) -> None:
        logger.info("Processing example job: %s", job.payload)

    asyncio.run(runner.run())


if __name__ == "__main__":
    main()
