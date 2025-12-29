"""
Distributed locks and concurrent job caps module.

Provides Redis-based distributed locking for:
- Concurrent crawl limits per project (max 1)
- Concurrent export limits per project (max 3)
- Global Common Crawl ingestion lock (max 1)

Returns 409 Conflict if cap exceeded.
"""

from semrush_core.locks.config import JobLimitsConfig
from semrush_core.locks.distributed_lock import DistributedLock, JobType
from semrush_core.locks.job_limiter import (
    JobLimiter,
    build_cc_ingestion_key,
    build_crawl_slot_key,
    build_export_slot_key,
)

__all__ = [
    "DistributedLock",
    "JobType",
    "JobLimiter",
    "JobLimitsConfig",
    "build_crawl_slot_key",
    "build_export_slot_key",
    "build_cc_ingestion_key",
]
