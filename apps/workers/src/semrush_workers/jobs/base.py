"""
Base Job class for background job processing.

Provides common functionality for all job types including:
- Job serialization/deserialization
- Retry logic with exponential backoff
- Lifecycle callbacks (on_success, on_failure)
"""

from __future__ import annotations

import random
import uuid
from abc import abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class JobType(StrEnum):
    """Types of background jobs."""

    SYNC = "sync"
    PROPERTY_SYNC = "property_sync"
    BACKFILL = "backfill"


@dataclass
class Job:
    """
    Base job class for background processing.

    Attributes:
        job_id: Unique job identifier.
        job_type: Type of job (sync, property_sync, backfill).
        payload: Job-specific data.
        attempts: Number of execution attempts.
        max_retries: Maximum retry attempts.
        created_at: When the job was created.
        last_error: Last error message if any.
        scheduled_at: When the job is scheduled to run.
        started_at: When execution started.
        completed_at: When execution completed.
    """

    job_id: str
    job_type: JobType
    payload: dict[str, Any]
    attempts: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_error: str | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Callbacks (not serialized)
    on_success: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = field(
        default=None, repr=False, compare=False
    )
    on_failure: Callable[[Exception], Coroutine[Any, Any, None]] | None = field(
        default=None, repr=False, compare=False
    )

    @property
    def can_retry(self) -> bool:
        """Check if the job can be retried."""
        return self.attempts < self.max_retries

    def get_backoff_delay(self, with_jitter: bool = False) -> float:
        """
        Calculate exponential backoff delay.

        Uses formula: base_delay * 2^(attempts-1)
        With optional jitter to prevent thundering herd.

        Args:
            with_jitter: Add random jitter to delay.

        Returns:
            Delay in seconds before next retry.
        """
        from semrush_workers.config import get_worker_config

        config = get_worker_config()
        base_delay = config.base_backoff_seconds

        # Exponential backoff: 30, 60, 120, 240...
        delay = base_delay * (2 ** max(0, self.attempts - 1))

        if with_jitter:
            # Add +/- 50% jitter
            jitter_factor = 0.5 + random.random()  # 0.5 to 1.5
            delay = delay * jitter_factor

        return delay

    def record_attempt(self) -> None:
        """Record a job execution attempt."""
        self.attempts += 1
        self.started_at = datetime.now(UTC)

    def record_error(self, error: str) -> None:
        """Record an error from the last attempt."""
        self.last_error = error

    def mark_completed(self) -> None:
        """Mark the job as completed."""
        self.completed_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize job to dictionary.

        Returns:
            Dictionary representation of the job.
        """
        return {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "payload": self.payload,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat(),
            "last_error": self.last_error,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        """
        Deserialize job from dictionary.

        Args:
            data: Dictionary representation of the job.

        Returns:
            Job instance.
        """
        return cls(
            job_id=data["job_id"],
            job_type=JobType(data["job_type"]),
            payload=data["payload"],
            attempts=data.get("attempts", 0),
            max_retries=data.get("max_retries", 3),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_error=data.get("last_error"),
            scheduled_at=(
                datetime.fromisoformat(data["scheduled_at"])
                if data.get("scheduled_at")
                else None
            ),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
        )

    @abstractmethod
    async def execute(
        self,
        db_session: AsyncSession,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Execute the job.

        Args:
            db_session: Database session for persistence.
            **kwargs: Additional job-specific dependencies.

        Returns:
            Result dictionary with 'success' key and job-specific data.
        """
        raise NotImplementedError("Subclasses must implement execute()")

    @staticmethod
    def generate_id() -> str:
        """Generate a unique job ID."""
        return str(uuid.uuid4())
