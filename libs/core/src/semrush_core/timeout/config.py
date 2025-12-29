"""
Timeout configuration.
"""

from __future__ import annotations

from datetime import timedelta

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TimeoutConfig(BaseSettings):
    """
    Configuration for job timeouts.

    Defaults:
    - Crawl: 4 hours (14400 seconds)
    - Export: 30 minutes (1800 seconds)
    """

    model_config = SettingsConfigDict(
        env_prefix="JOB_TIMEOUT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    crawl_timeout_seconds: int = Field(
        default=14400,  # 4 hours
        ge=60,
        description="Crawl job timeout in seconds",
    )

    export_timeout_seconds: int = Field(
        default=1800,  # 30 minutes
        ge=60,
        description="Export job timeout in seconds",
    )

    @property
    def crawl_timeout(self) -> timedelta:
        """Get crawl timeout as timedelta."""
        return timedelta(seconds=self.crawl_timeout_seconds)

    @property
    def export_timeout(self) -> timedelta:
        """Get export timeout as timedelta."""
        return timedelta(seconds=self.export_timeout_seconds)
