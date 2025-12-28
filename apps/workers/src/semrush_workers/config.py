"""
Worker configuration using pydantic-settings.

Configuration for background job processing including Redis connection,
concurrency limits, and scheduling parameters.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerConfig(BaseSettings):
    """
    Worker configuration loaded from environment variables.

    Attributes:
        redis_url: Redis connection URL for job queue.
        max_concurrent_jobs: Maximum jobs to process concurrently.
        poll_interval: Seconds between queue polls.
        job_timeout: Maximum job execution time in seconds.
        daily_sync_hour_utc: Hour (0-23) for daily sync in UTC.
        backfill_months: Number of months to backfill for GSC/GA4.
        max_retries: Maximum retry attempts for failed jobs.
        base_backoff_seconds: Base backoff delay for retries.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # Concurrency settings
    max_concurrent_jobs: int = Field(
        default=10,
        ge=1,
        le=100,
        alias="WORKER_MAX_CONCURRENT_JOBS",
        description="Maximum concurrent job executions",
    )

    # Polling settings
    poll_interval: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        alias="WORKER_POLL_INTERVAL",
        description="Seconds between queue polls",
    )

    # Job execution settings
    job_timeout: int = Field(
        default=300,
        ge=10,
        le=3600,
        alias="WORKER_JOB_TIMEOUT",
        description="Maximum job execution time in seconds",
    )

    # Scheduling settings
    daily_sync_hour_utc: int = Field(
        default=2,
        ge=0,
        le=23,
        alias="WORKER_DAILY_SYNC_HOUR_UTC",
        description="Hour for daily sync in UTC (0-23)",
    )

    # Backfill settings
    backfill_months: int = Field(
        default=16,
        ge=1,
        le=36,
        alias="WORKER_BACKFILL_MONTHS",
        description="Number of months to backfill for GSC/GA4",
    )

    # Retry settings
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        alias="WORKER_MAX_RETRIES",
        description="Maximum retry attempts for failed jobs",
    )

    base_backoff_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        alias="WORKER_BASE_BACKOFF_SECONDS",
        description="Base backoff delay in seconds for retries",
    )

    # Job data retention
    job_data_ttl_days: int = Field(
        default=7,
        ge=1,
        le=90,
        alias="WORKER_JOB_DATA_TTL_DAYS",
        description="Days to retain completed job data",
    )

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must start with redis:// or rediss://")
        return v

    @property
    def job_data_ttl_seconds(self) -> int:
        """Get job data TTL in seconds."""
        return self.job_data_ttl_days * 24 * 60 * 60


@lru_cache
def get_worker_config() -> WorkerConfig:
    """
    Get cached worker configuration.

    Returns:
        WorkerConfig instance with validated settings.
    """
    return WorkerConfig()
