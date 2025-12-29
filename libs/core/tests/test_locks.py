"""
Tests for distributed locks and concurrent job caps.

Uses TDD approach - tests are written first to define expected behavior.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest


class TestDistributedLockConfig:
    """Tests for distributed lock configuration."""

    def test_job_type_enum_has_required_values(self) -> None:
        from semrush_core.locks.distributed_lock import JobType

        assert hasattr(JobType, "CRAWL")
        assert hasattr(JobType, "EXPORT")
        assert hasattr(JobType, "CC_INGESTION")

    def test_job_limits_config_has_crawl_limit(self) -> None:
        from semrush_core.locks.config import JobLimitsConfig

        config = JobLimitsConfig()
        assert config.max_concurrent_crawls_per_project == 1

    def test_job_limits_config_has_export_limit(self) -> None:
        from semrush_core.locks.config import JobLimitsConfig

        config = JobLimitsConfig()
        assert config.max_concurrent_exports_per_project == 3

    def test_job_limits_config_has_cc_ingestion_limit(self) -> None:
        from semrush_core.locks.config import JobLimitsConfig

        config = JobLimitsConfig()
        assert config.max_concurrent_cc_ingestion_global == 1

    def test_job_limits_config_has_default_ttl(self) -> None:
        from semrush_core.locks.config import JobLimitsConfig

        config = JobLimitsConfig()
        assert config.crawl_lock_ttl_seconds == 14400  # 4 hours
        assert config.export_lock_ttl_seconds == 1800  # 30 minutes
        assert config.cc_ingestion_lock_ttl_seconds == 86400  # 24 hours


class TestDistributedLock:
    """Tests for distributed lock implementation."""

    @pytest.mark.asyncio
    async def test_init_creates_redis_client(self) -> None:
        from semrush_core.locks.distributed_lock import DistributedLock

        with patch("semrush_core.locks.distributed_lock.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.from_url.return_value = mock_client

            lock = DistributedLock(redis_url="redis://localhost:6379/0")

            mock_redis_class.from_url.assert_called_once()
            assert lock._client == mock_client

    @pytest.mark.asyncio
    async def test_acquire_returns_true_when_lock_available(self) -> None:
        from semrush_core.locks.distributed_lock import DistributedLock

        with patch("semrush_core.locks.distributed_lock.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.set.return_value = True  # Lock acquired
            mock_redis_class.from_url.return_value = mock_client

            lock = DistributedLock(redis_url="redis://localhost:6379/0")
            acquired = await lock.acquire(
                key="lock:crawl:proj-123",
                owner="worker-1",
                ttl_seconds=300,
            )

            assert acquired is True

    @pytest.mark.asyncio
    async def test_acquire_returns_false_when_lock_held(self) -> None:
        from semrush_core.locks.distributed_lock import DistributedLock

        with patch("semrush_core.locks.distributed_lock.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.set.return_value = None  # Lock already held
            mock_redis_class.from_url.return_value = mock_client

            lock = DistributedLock(redis_url="redis://localhost:6379/0")
            acquired = await lock.acquire(
                key="lock:crawl:proj-123",
                owner="worker-2",
                ttl_seconds=300,
            )

            assert acquired is False

    @pytest.mark.asyncio
    async def test_acquire_uses_nx_flag(self) -> None:
        from semrush_core.locks.distributed_lock import DistributedLock

        with patch("semrush_core.locks.distributed_lock.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.set.return_value = True
            mock_redis_class.from_url.return_value = mock_client

            lock = DistributedLock(redis_url="redis://localhost:6379/0")
            await lock.acquire(key="lock:test", owner="worker-1", ttl_seconds=300)

            # Should use NX flag (only set if not exists)
            mock_client.set.assert_called_once()
            call_kwargs = mock_client.set.call_args.kwargs
            assert call_kwargs.get("nx") is True

    @pytest.mark.asyncio
    async def test_acquire_sets_expiry(self) -> None:
        from semrush_core.locks.distributed_lock import DistributedLock

        with patch("semrush_core.locks.distributed_lock.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.set.return_value = True
            mock_redis_class.from_url.return_value = mock_client

            lock = DistributedLock(redis_url="redis://localhost:6379/0")
            await lock.acquire(key="lock:test", owner="worker-1", ttl_seconds=300)

            # Should set TTL
            call_kwargs = mock_client.set.call_args.kwargs
            assert call_kwargs.get("ex") == 300

    @pytest.mark.asyncio
    async def test_release_removes_lock_when_owner_matches(self) -> None:
        from semrush_core.locks.distributed_lock import DistributedLock

        with patch("semrush_core.locks.distributed_lock.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = "worker-1"  # Current owner
            mock_client.delete.return_value = 1
            mock_redis_class.from_url.return_value = mock_client

            lock = DistributedLock(redis_url="redis://localhost:6379/0")
            released = await lock.release(key="lock:test", owner="worker-1")

            assert released is True
            mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_returns_false_when_owner_mismatch(self) -> None:
        from semrush_core.locks.distributed_lock import DistributedLock

        with patch("semrush_core.locks.distributed_lock.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = "worker-1"  # Different owner
            mock_redis_class.from_url.return_value = mock_client

            lock = DistributedLock(redis_url="redis://localhost:6379/0")
            released = await lock.release(key="lock:test", owner="worker-2")

            assert released is False
            mock_client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_release_returns_false_when_lock_not_found(self) -> None:
        from semrush_core.locks.distributed_lock import DistributedLock

        with patch("semrush_core.locks.distributed_lock.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = None  # Lock not found
            mock_redis_class.from_url.return_value = mock_client

            lock = DistributedLock(redis_url="redis://localhost:6379/0")
            released = await lock.release(key="lock:test", owner="worker-1")

            assert released is False

    @pytest.mark.asyncio
    async def test_is_locked_returns_true_when_lock_exists(self) -> None:
        from semrush_core.locks.distributed_lock import DistributedLock

        with patch("semrush_core.locks.distributed_lock.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.exists.return_value = 1
            mock_redis_class.from_url.return_value = mock_client

            lock = DistributedLock(redis_url="redis://localhost:6379/0")
            is_locked = await lock.is_locked(key="lock:test")

            assert is_locked is True

    @pytest.mark.asyncio
    async def test_is_locked_returns_false_when_no_lock(self) -> None:
        from semrush_core.locks.distributed_lock import DistributedLock

        with patch("semrush_core.locks.distributed_lock.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.exists.return_value = 0
            mock_redis_class.from_url.return_value = mock_client

            lock = DistributedLock(redis_url="redis://localhost:6379/0")
            is_locked = await lock.is_locked(key="lock:test")

            assert is_locked is False

    @pytest.mark.asyncio
    async def test_refresh_extends_ttl_when_owner_matches(self) -> None:
        from semrush_core.locks.distributed_lock import DistributedLock

        with patch("semrush_core.locks.distributed_lock.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = "worker-1"
            mock_client.expire.return_value = True
            mock_redis_class.from_url.return_value = mock_client

            lock = DistributedLock(redis_url="redis://localhost:6379/0")
            refreshed = await lock.refresh(key="test", owner="worker-1", ttl_seconds=600)

            assert refreshed is True
            # Full key is prefix + key = "lock:test"
            mock_client.expire.assert_called_once_with("lock:test", 600)

    @pytest.mark.asyncio
    async def test_close_closes_redis_connection(self) -> None:
        from semrush_core.locks.distributed_lock import DistributedLock

        with patch("semrush_core.locks.distributed_lock.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.from_url.return_value = mock_client

            lock = DistributedLock(redis_url="redis://localhost:6379/0")
            await lock.close()

            mock_client.close.assert_called_once()


class TestJobLimiter:
    """Tests for job limiter that enforces concurrent job caps."""

    @pytest.mark.asyncio
    async def test_acquire_crawl_slot_succeeds_when_under_limit(self) -> None:
        from semrush_core.locks.job_limiter import JobLimiter

        with patch("semrush_core.locks.job_limiter.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.scard.return_value = 0  # No active crawls
            mock_client.sadd.return_value = 1
            mock_redis_class.from_url.return_value = mock_client

            limiter = JobLimiter(redis_url="redis://localhost:6379/0")
            acquired, job_id = await limiter.acquire_crawl_slot(
                project_id="proj-123",
            )

            assert acquired is True
            assert job_id is not None

    @pytest.mark.asyncio
    async def test_acquire_crawl_slot_fails_when_at_limit(self) -> None:
        from semrush_core.locks.job_limiter import JobLimiter

        with patch("semrush_core.locks.job_limiter.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.scard.return_value = 1  # Already 1 active crawl (limit is 1)
            mock_redis_class.from_url.return_value = mock_client

            limiter = JobLimiter(redis_url="redis://localhost:6379/0")
            acquired, job_id = await limiter.acquire_crawl_slot(
                project_id="proj-123",
            )

            assert acquired is False
            assert job_id is None

    @pytest.mark.asyncio
    async def test_acquire_export_slot_succeeds_when_under_limit(self) -> None:
        from semrush_core.locks.job_limiter import JobLimiter

        with patch("semrush_core.locks.job_limiter.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.scard.return_value = 2  # 2 active exports (limit is 3)
            mock_client.sadd.return_value = 1
            mock_redis_class.from_url.return_value = mock_client

            limiter = JobLimiter(redis_url="redis://localhost:6379/0")
            acquired, job_id = await limiter.acquire_export_slot(
                project_id="proj-123",
            )

            assert acquired is True
            assert job_id is not None

    @pytest.mark.asyncio
    async def test_acquire_export_slot_fails_when_at_limit(self) -> None:
        from semrush_core.locks.job_limiter import JobLimiter

        with patch("semrush_core.locks.job_limiter.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.scard.return_value = 3  # 3 active exports (limit is 3)
            mock_redis_class.from_url.return_value = mock_client

            limiter = JobLimiter(redis_url="redis://localhost:6379/0")
            acquired, job_id = await limiter.acquire_export_slot(
                project_id="proj-123",
            )

            assert acquired is False
            assert job_id is None

    @pytest.mark.asyncio
    async def test_acquire_cc_ingestion_slot_is_global(self) -> None:
        from semrush_core.locks.job_limiter import JobLimiter

        with patch("semrush_core.locks.job_limiter.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.set.return_value = True
            mock_redis_class.from_url.return_value = mock_client

            limiter = JobLimiter(redis_url="redis://localhost:6379/0")
            acquired, job_id = await limiter.acquire_cc_ingestion_slot()

            assert acquired is True
            # Should use a global key, not per-project
            mock_client.set.assert_called()

    @pytest.mark.asyncio
    async def test_acquire_cc_ingestion_slot_fails_when_active(self) -> None:
        from semrush_core.locks.job_limiter import JobLimiter

        with patch("semrush_core.locks.job_limiter.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.set.return_value = None  # Lock already held
            mock_redis_class.from_url.return_value = mock_client

            limiter = JobLimiter(redis_url="redis://localhost:6379/0")
            acquired, job_id = await limiter.acquire_cc_ingestion_slot()

            assert acquired is False
            assert job_id is None

    @pytest.mark.asyncio
    async def test_release_crawl_slot_removes_job(self) -> None:
        from semrush_core.locks.job_limiter import JobLimiter

        with patch("semrush_core.locks.job_limiter.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.srem.return_value = 1
            mock_redis_class.from_url.return_value = mock_client

            limiter = JobLimiter(redis_url="redis://localhost:6379/0")
            released = await limiter.release_crawl_slot(
                project_id="proj-123",
                job_id="job-456",
            )

            assert released is True
            mock_client.srem.assert_called()

    @pytest.mark.asyncio
    async def test_release_export_slot_removes_job(self) -> None:
        from semrush_core.locks.job_limiter import JobLimiter

        with patch("semrush_core.locks.job_limiter.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.srem.return_value = 1
            mock_redis_class.from_url.return_value = mock_client

            limiter = JobLimiter(redis_url="redis://localhost:6379/0")
            released = await limiter.release_export_slot(
                project_id="proj-123",
                job_id="job-456",
            )

            assert released is True

    @pytest.mark.asyncio
    async def test_release_cc_ingestion_slot_removes_lock(self) -> None:
        from semrush_core.locks.job_limiter import JobLimiter

        with patch("semrush_core.locks.job_limiter.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = "job-456"
            mock_client.delete.return_value = 1
            mock_redis_class.from_url.return_value = mock_client

            limiter = JobLimiter(redis_url="redis://localhost:6379/0")
            released = await limiter.release_cc_ingestion_slot(job_id="job-456")

            assert released is True

    @pytest.mark.asyncio
    async def test_get_active_crawls_returns_count(self) -> None:
        from semrush_core.locks.job_limiter import JobLimiter

        with patch("semrush_core.locks.job_limiter.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.scard.return_value = 1
            mock_redis_class.from_url.return_value = mock_client

            limiter = JobLimiter(redis_url="redis://localhost:6379/0")
            count = await limiter.get_active_crawls(project_id="proj-123")

            assert count == 1

    @pytest.mark.asyncio
    async def test_get_active_exports_returns_count(self) -> None:
        from semrush_core.locks.job_limiter import JobLimiter

        with patch("semrush_core.locks.job_limiter.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.scard.return_value = 2
            mock_redis_class.from_url.return_value = mock_client

            limiter = JobLimiter(redis_url="redis://localhost:6379/0")
            count = await limiter.get_active_exports(project_id="proj-123")

            assert count == 2


class TestJobLimiterKeyGeneration:
    """Tests for job limiter key generation."""

    def test_build_crawl_key_includes_project_id(self) -> None:
        from semrush_core.locks.job_limiter import build_crawl_slot_key

        key = build_crawl_slot_key(project_id="proj-123")
        assert key == "jobs:crawl:proj-123"

    def test_build_export_key_includes_project_id(self) -> None:
        from semrush_core.locks.job_limiter import build_export_slot_key

        key = build_export_slot_key(project_id="proj-456")
        assert key == "jobs:export:proj-456"

    def test_build_cc_ingestion_key_is_global(self) -> None:
        from semrush_core.locks.job_limiter import build_cc_ingestion_key

        key = build_cc_ingestion_key()
        assert key == "jobs:cc_ingestion:global"
