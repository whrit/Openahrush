"""
Configuration for distributed locks and job limits.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class JobLimitsConfig(BaseSettings):
    """
    Configuration for concurrent job limits.

    Defaults are optimized for typical self-hosted deployments:
    - 1 concurrent crawl per project to prevent resource exhaustion
    - 3 concurrent exports per project for reasonable parallelism
    - 1 global CC ingestion to prevent overwhelming the data plane
    """

    model_config = SettingsConfigDict(
        env_prefix="JOB_LIMIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Concurrent crawl limit per project
    max_concurrent_crawls_per_project: int = Field(
        default=1,
        ge=1,
        description="Max concurrent crawls per project",
    )

    # Concurrent export limit per project
    max_concurrent_exports_per_project: int = Field(
        default=3,
        ge=1,
        description="Max concurrent exports per project",
    )

    # Global CC ingestion limit
    max_concurrent_cc_ingestion_global: int = Field(
        default=1,
        ge=1,
        description="Max concurrent Common Crawl ingestions globally",
    )

    # Lock TTL values
    crawl_lock_ttl_seconds: int = Field(
        default=14400,  # 4 hours
        ge=60,
        description="TTL for crawl locks in seconds",
    )

    export_lock_ttl_seconds: int = Field(
        default=1800,  # 30 minutes
        ge=60,
        description="TTL for export locks in seconds",
    )

    cc_ingestion_lock_ttl_seconds: int = Field(
        default=86400,  # 24 hours
        ge=3600,
        description="TTL for CC ingestion lock in seconds",
    )
