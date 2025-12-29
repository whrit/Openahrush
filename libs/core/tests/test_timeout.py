"""
Tests for job timeout enforcement.

Uses TDD approach - tests are written first to define expected behavior.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestTimeoutConfig:
    """Tests for timeout configuration."""

    def test_crawl_timeout_is_4_hours(self) -> None:
        from semrush_core.timeout.config import TimeoutConfig

        config = TimeoutConfig()
        assert config.crawl_timeout_seconds == 14400  # 4 hours

    def test_export_timeout_is_30_minutes(self) -> None:
        from semrush_core.timeout.config import TimeoutConfig

        config = TimeoutConfig()
        assert config.export_timeout_seconds == 1800  # 30 minutes

    def test_config_provides_timedelta(self) -> None:
        from semrush_core.timeout.config import TimeoutConfig

        config = TimeoutConfig()
        assert config.crawl_timeout == timedelta(hours=4)
        assert config.export_timeout == timedelta(minutes=30)


class TestTimeoutEnforcer:
    """Tests for timeout enforcement service."""

    def test_check_crawl_timeout_returns_false_when_not_timed_out(self) -> None:
        from semrush_core.timeout.enforcer import TimeoutEnforcer

        enforcer = TimeoutEnforcer()

        # Started 1 hour ago (within 4 hour limit)
        started_at = datetime.now(UTC) - timedelta(hours=1)

        is_timed_out = enforcer.is_crawl_timed_out(started_at=started_at)

        assert is_timed_out is False

    def test_check_crawl_timeout_returns_true_when_timed_out(self) -> None:
        from semrush_core.timeout.enforcer import TimeoutEnforcer

        enforcer = TimeoutEnforcer()

        # Started 5 hours ago (exceeded 4 hour limit)
        started_at = datetime.now(UTC) - timedelta(hours=5)

        is_timed_out = enforcer.is_crawl_timed_out(started_at=started_at)

        assert is_timed_out is True

    def test_check_export_timeout_returns_false_when_not_timed_out(self) -> None:
        from semrush_core.timeout.enforcer import TimeoutEnforcer

        enforcer = TimeoutEnforcer()

        # Started 15 minutes ago (within 30 minute limit)
        started_at = datetime.now(UTC) - timedelta(minutes=15)

        is_timed_out = enforcer.is_export_timed_out(started_at=started_at)

        assert is_timed_out is False

    def test_check_export_timeout_returns_true_when_timed_out(self) -> None:
        from semrush_core.timeout.enforcer import TimeoutEnforcer

        enforcer = TimeoutEnforcer()

        # Started 45 minutes ago (exceeded 30 minute limit)
        started_at = datetime.now(UTC) - timedelta(minutes=45)

        is_timed_out = enforcer.is_export_timed_out(started_at=started_at)

        assert is_timed_out is True

    def test_get_remaining_crawl_time(self) -> None:
        from semrush_core.timeout.enforcer import TimeoutEnforcer

        enforcer = TimeoutEnforcer()

        # Started 1 hour ago
        started_at = datetime.now(UTC) - timedelta(hours=1)

        remaining = enforcer.get_remaining_crawl_time(started_at=started_at)

        # Should have about 3 hours remaining
        assert remaining.total_seconds() > 0
        assert remaining.total_seconds() <= 3 * 3600 + 60  # Allow 1 min tolerance

    def test_get_remaining_export_time(self) -> None:
        from semrush_core.timeout.enforcer import TimeoutEnforcer

        enforcer = TimeoutEnforcer()

        # Started 10 minutes ago
        started_at = datetime.now(UTC) - timedelta(minutes=10)

        remaining = enforcer.get_remaining_export_time(started_at=started_at)

        # Should have about 20 minutes remaining
        assert remaining.total_seconds() > 0
        assert remaining.total_seconds() <= 20 * 60 + 60  # Allow 1 min tolerance

    def test_get_remaining_time_returns_zero_when_exceeded(self) -> None:
        from semrush_core.timeout.enforcer import TimeoutEnforcer

        enforcer = TimeoutEnforcer()

        # Started 5 hours ago (exceeded)
        started_at = datetime.now(UTC) - timedelta(hours=5)

        remaining = enforcer.get_remaining_crawl_time(started_at=started_at)

        assert remaining.total_seconds() <= 0


class TestTimeoutJobMarker:
    """Tests for marking jobs as timed out."""

    @pytest.mark.asyncio
    async def test_mark_crawl_as_timed_out(self) -> None:
        from semrush_core.models import CrawlStatus
        from semrush_core.timeout.enforcer import TimeoutEnforcer

        crawl_run = MagicMock()
        crawl_run.status = CrawlStatus.RUNNING
        crawl_run.error_message = None
        crawl_run.finished_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = crawl_run

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        enforcer = TimeoutEnforcer()
        await enforcer.mark_crawl_timed_out(
            session=mock_session,
            crawl_id=uuid.uuid4(),
        )

        assert crawl_run.status == CrawlStatus.FAILED
        assert "timed out" in crawl_run.error_message.lower()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_export_as_timed_out(self) -> None:
        from semrush_core.models import ExportStatus
        from semrush_core.timeout.enforcer import TimeoutEnforcer

        export = MagicMock()
        export.status = ExportStatus.RUNNING
        export.error_message = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = export

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        enforcer = TimeoutEnforcer()
        await enforcer.mark_export_timed_out(
            session=mock_session,
            export_id=uuid.uuid4(),
        )

        assert export.status == ExportStatus.FAILED
        assert "timed out" in export.error_message.lower()
        mock_session.flush.assert_called_once()


class TestTimeoutCheckerService:
    """Tests for background timeout checker service."""

    @pytest.mark.asyncio
    async def test_check_timed_out_crawls_finds_expired(self) -> None:
        from semrush_core.models import CrawlStatus
        from semrush_core.timeout.enforcer import TimeoutEnforcer

        # Create mock crawl that started 5 hours ago
        timed_out_crawl = MagicMock()
        timed_out_crawl.id = uuid.uuid4()
        timed_out_crawl.started_at = datetime.now(UTC) - timedelta(hours=5)
        timed_out_crawl.status = CrawlStatus.RUNNING
        timed_out_crawl.error_message = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [timed_out_crawl]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        enforcer = TimeoutEnforcer()
        timed_out = await enforcer.find_timed_out_crawls(session=mock_session)

        assert len(timed_out) == 1
        assert timed_out[0].id == timed_out_crawl.id

    @pytest.mark.asyncio
    async def test_check_timed_out_exports_finds_expired(self) -> None:
        from semrush_core.models import ExportStatus
        from semrush_core.timeout.enforcer import TimeoutEnforcer

        # Create mock export that started 45 minutes ago
        timed_out_export = MagicMock()
        timed_out_export.id = uuid.uuid4()
        timed_out_export.created_at = datetime.now(UTC) - timedelta(minutes=45)
        timed_out_export.status = ExportStatus.RUNNING
        timed_out_export.error_message = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [timed_out_export]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        enforcer = TimeoutEnforcer()
        timed_out = await enforcer.find_timed_out_exports(session=mock_session)

        assert len(timed_out) == 1
        assert timed_out[0].id == timed_out_export.id

    @pytest.mark.asyncio
    async def test_process_timed_out_jobs_marks_all_as_failed(self) -> None:
        from semrush_core.models import CrawlStatus
        from semrush_core.timeout.enforcer import TimeoutEnforcer

        # Create mock crawls
        crawl1 = MagicMock()
        crawl1.id = uuid.uuid4()
        crawl1.started_at = datetime.now(UTC) - timedelta(hours=5)
        crawl1.status = CrawlStatus.RUNNING
        crawl1.error_message = None
        crawl1.finished_at = None

        crawl2 = MagicMock()
        crawl2.id = uuid.uuid4()
        crawl2.started_at = datetime.now(UTC) - timedelta(hours=6)
        crawl2.status = CrawlStatus.RUNNING
        crawl2.error_message = None
        crawl2.finished_at = None

        mock_session = AsyncMock()

        enforcer = TimeoutEnforcer()
        count = await enforcer.process_timed_out_crawls(
            session=mock_session,
            crawls=[crawl1, crawl2],
        )

        assert count == 2
        assert crawl1.status == CrawlStatus.FAILED
        assert crawl2.status == CrawlStatus.FAILED


class TestTimeoutError:
    """Tests for timeout error class."""

    def test_timeout_error_has_job_type(self) -> None:
        from semrush_core.timeout.errors import JobTimeoutError

        error = JobTimeoutError(
            job_type="crawl",
            job_id=uuid.uuid4(),
            started_at=datetime.now(UTC) - timedelta(hours=5),
            timeout_seconds=14400,
        )

        assert error.job_type == "crawl"
        assert "timed out" in str(error).lower()

    def test_timeout_error_has_elapsed_time(self) -> None:
        from semrush_core.timeout.errors import JobTimeoutError

        started = datetime.now(UTC) - timedelta(hours=5)
        error = JobTimeoutError(
            job_type="crawl",
            job_id=uuid.uuid4(),
            started_at=started,
            timeout_seconds=14400,
        )

        assert error.elapsed_seconds > 0
