"""
Timeout error classes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


class JobTimeoutError(Exception):
    """Exception raised when a job exceeds its timeout."""

    def __init__(
        self,
        job_type: str,
        job_id: uuid.UUID,
        started_at: datetime,
        timeout_seconds: int,
    ) -> None:
        """
        Initialize the timeout error.

        Args:
            job_type: Type of job (crawl, export).
            job_id: The job identifier.
            started_at: When the job started.
            timeout_seconds: The timeout limit.
        """
        self.job_type = job_type
        self.job_id = job_id
        self.started_at = started_at
        self.timeout_seconds = timeout_seconds

        elapsed = datetime.now(UTC) - started_at
        self._elapsed_seconds = elapsed.total_seconds()

        super().__init__(
            f"{job_type.capitalize()} job {job_id} timed out after "
            f"{self._elapsed_seconds:.0f}s (limit: {timeout_seconds}s)"
        )

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return self._elapsed_seconds
