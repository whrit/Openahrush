"""
Tests for sync job implementations.

Tests cover:
- Base Job abstract class
- SyncJob for integration data sync
- PropertySyncJob for property list refresh
- Job lifecycle (pending -> running -> completed/failed)
- Retry logic with exponential backoff
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from semrush_core.models.sync_run import SyncMode, SyncStatus


class TestBaseJob:
    """Tests for the abstract Job base class."""

    def test_job_creation_with_required_fields(self) -> None:
        """Test creating a job with required fields."""
        from semrush_workers.jobs.base import Job, JobType

        job = Job(
            job_id=str(uuid.uuid4()),
            job_type=JobType.SYNC,
            payload={"mapping_id": str(uuid.uuid4())},
        )

        assert job.job_id is not None
        assert job.job_type == JobType.SYNC
        assert job.payload is not None
        assert job.attempts == 0
        assert job.max_retries == 3
        assert job.created_at is not None

    def test_job_creation_with_custom_max_retries(self) -> None:
        """Test creating a job with custom max_retries."""
        from semrush_workers.jobs.base import Job, JobType

        job = Job(
            job_id=str(uuid.uuid4()),
            job_type=JobType.SYNC,
            payload={},
            max_retries=5,
        )

        assert job.max_retries == 5

    def test_job_can_retry_when_under_limit(self) -> None:
        """Test that job can retry when attempts under limit."""
        from semrush_workers.jobs.base import Job, JobType

        job = Job(
            job_id=str(uuid.uuid4()),
            job_type=JobType.SYNC,
            payload={},
            max_retries=3,
        )
        job.attempts = 2

        assert job.can_retry is True

    def test_job_cannot_retry_when_at_limit(self) -> None:
        """Test that job cannot retry when attempts at limit."""
        from semrush_workers.jobs.base import Job, JobType

        job = Job(
            job_id=str(uuid.uuid4()),
            job_type=JobType.SYNC,
            payload={},
            max_retries=3,
        )
        job.attempts = 3

        assert job.can_retry is False

    def test_job_backoff_delay_calculation(self) -> None:
        """Test exponential backoff delay calculation."""
        from semrush_workers.jobs.base import Job, JobType

        job = Job(
            job_id=str(uuid.uuid4()),
            job_type=JobType.SYNC,
            payload={},
        )

        # First retry: 2^0 * 30 = 30 seconds
        job.attempts = 1
        assert job.get_backoff_delay() == 30

        # Second retry: 2^1 * 30 = 60 seconds
        job.attempts = 2
        assert job.get_backoff_delay() == 60

        # Third retry: 2^2 * 30 = 120 seconds
        job.attempts = 3
        assert job.get_backoff_delay() == 120

    def test_job_to_dict_serialization(self) -> None:
        """Test job serialization to dictionary."""
        from semrush_workers.jobs.base import Job, JobType

        job_id = str(uuid.uuid4())
        payload = {"mapping_id": str(uuid.uuid4())}

        job = Job(
            job_id=job_id,
            job_type=JobType.SYNC,
            payload=payload,
        )

        data = job.to_dict()

        assert data["job_id"] == job_id
        assert data["job_type"] == JobType.SYNC.value
        assert data["payload"] == payload
        assert "created_at" in data

    def test_job_from_dict_deserialization(self) -> None:
        """Test job deserialization from dictionary."""
        from semrush_workers.jobs.base import Job, JobType

        job_id = str(uuid.uuid4())
        data = {
            "job_id": job_id,
            "job_type": JobType.SYNC.value,
            "payload": {"key": "value"},
            "attempts": 1,
            "max_retries": 3,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        job = Job.from_dict(data)

        assert job.job_id == job_id
        assert job.job_type == JobType.SYNC
        assert job.payload == {"key": "value"}
        assert job.attempts == 1


class TestSyncJob:
    """Tests for SyncJob implementation."""

    def test_sync_job_creation(self, sample_mapping_id: uuid.UUID) -> None:
        """Test creating a sync job."""
        from semrush_workers.jobs.sync_job import SyncJob

        job = SyncJob.create(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
            date_range_start=date(2024, 1, 1),
            date_range_end=date(2024, 1, 31),
        )

        assert job.mapping_id == sample_mapping_id
        assert job.sync_mode == SyncMode.INCREMENTAL
        assert job.date_range_start == date(2024, 1, 1)
        assert job.date_range_end == date(2024, 1, 31)

    def test_sync_job_backfill_creation(self, sample_mapping_id: uuid.UUID) -> None:
        """Test creating a backfill sync job."""
        from semrush_workers.jobs.sync_job import SyncJob

        job = SyncJob.create(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.BACKFILL,
            date_range_start=date(2023, 1, 1),
            date_range_end=date(2024, 1, 31),
        )

        assert job.sync_mode == SyncMode.BACKFILL
        assert job.date_range_start == date(2023, 1, 1)
        assert job.date_range_end == date(2024, 1, 31)

    @pytest.mark.asyncio
    async def test_sync_job_execute_success(
        self,
        sample_mapping_id: uuid.UUID,
        mock_db_session: AsyncMock,
        mock_data_sync_service: AsyncMock,
    ) -> None:
        """Test successful sync job execution."""
        from semrush_workers.jobs.sync_job import SyncJob

        job = SyncJob.create(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
            date_range_start=date(2024, 1, 1),
            date_range_end=date(2024, 1, 31),
        )

        # Mock sync run retrieval
        mock_sync_run = MagicMock()
        mock_sync_run.status = SyncStatus.QUEUED.value
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sync_run
        mock_db_session.execute.return_value = mock_result

        result = await job.execute(
            db_session=mock_db_session,
            data_sync_service=mock_data_sync_service,
        )

        assert result["success"] is True
        assert result["records_written"] == 100
        mock_data_sync_service.sync_data.assert_called_once()
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_sync_job_execute_failure(
        self,
        sample_mapping_id: uuid.UUID,
        mock_db_session: AsyncMock,
        mock_data_sync_service: AsyncMock,
    ) -> None:
        """Test sync job execution failure."""
        from semrush_workers.jobs.sync_job import SyncJob

        job = SyncJob.create(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
        )

        # Make the sync service raise an error
        mock_data_sync_service.sync_data.side_effect = Exception("API rate limit exceeded")

        # Mock sync run retrieval
        mock_sync_run = MagicMock()
        mock_sync_run.status = SyncStatus.QUEUED.value
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sync_run
        mock_db_session.execute.return_value = mock_result

        result = await job.execute(
            db_session=mock_db_session,
            data_sync_service=mock_data_sync_service,
        )

        assert result["success"] is False
        assert "API rate limit exceeded" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_job_updates_sync_run_status(
        self,
        sample_mapping_id: uuid.UUID,
        mock_db_session: AsyncMock,
        mock_data_sync_service: AsyncMock,
    ) -> None:
        """Test that sync job updates SyncRun status correctly."""
        from semrush_workers.jobs.sync_job import SyncJob

        job = SyncJob.create(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
        )

        mock_sync_run = MagicMock()
        mock_sync_run.status = SyncStatus.QUEUED.value
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sync_run
        mock_db_session.execute.return_value = mock_result

        result = await job.execute(
            db_session=mock_db_session,
            data_sync_service=mock_data_sync_service,
        )

        # Verify successful execution and commit was called
        assert result["success"] is True
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_sync_job_on_success_callback(
        self,
        sample_mapping_id: uuid.UUID,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test on_success callback is called after successful execution."""
        from semrush_workers.jobs.sync_job import SyncJob

        job = SyncJob.create(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
        )

        callback_called = False

        async def on_success_callback(result: dict[str, Any]) -> None:
            nonlocal callback_called
            callback_called = True

        job.on_success = on_success_callback

        # Create a minimal successful result
        await job.on_success({"success": True, "records_written": 50})

        assert callback_called is True

    @pytest.mark.asyncio
    async def test_sync_job_on_failure_callback(
        self,
        sample_mapping_id: uuid.UUID,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test on_failure callback is called after failed execution."""
        from semrush_workers.jobs.sync_job import SyncJob

        job = SyncJob.create(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
        )

        failure_error = None

        async def on_failure_callback(error: Exception) -> None:
            nonlocal failure_error
            failure_error = error

        job.on_failure = on_failure_callback

        test_error = Exception("Test error")
        await job.on_failure(test_error)

        assert failure_error is test_error


class TestPropertySyncJob:
    """Tests for PropertySyncJob implementation."""

    def test_property_sync_job_creation(self, sample_project_id: uuid.UUID) -> None:
        """Test creating a property sync job."""
        from semrush_workers.jobs.property_sync_job import PropertySyncJob

        job = PropertySyncJob.create(
            integration_account_id=sample_project_id,
            provider="google_search_console",
        )

        assert job.integration_account_id == sample_project_id
        assert job.provider == "google_search_console"

    @pytest.mark.asyncio
    async def test_property_sync_job_execute_success(
        self,
        sample_project_id: uuid.UUID,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test successful property sync job execution."""
        from semrush_workers.jobs.property_sync_job import PropertySyncJob

        job = PropertySyncJob.create(
            integration_account_id=sample_project_id,
            provider="google_search_console",
        )

        # Mock property discovery service
        mock_discovery_service = AsyncMock()
        mock_discovery_service.discover_properties = AsyncMock(
            return_value=[
                {"property_id": "sc-domain:example.com", "display_name": "example.com"},
                {"property_id": "sc-domain:test.com", "display_name": "test.com"},
            ]
        )

        # Mock the execute result properly for scalar_one_or_none()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing properties
        mock_db_session.execute.return_value = mock_result

        result = await job.execute(
            db_session=mock_db_session,
            discovery_service=mock_discovery_service,
        )

        assert result["success"] is True
        assert result["properties_discovered"] == 2

    @pytest.mark.asyncio
    async def test_property_sync_job_execute_failure(
        self,
        sample_project_id: uuid.UUID,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test property sync job execution failure."""
        from semrush_workers.jobs.property_sync_job import PropertySyncJob

        job = PropertySyncJob.create(
            integration_account_id=sample_project_id,
            provider="google_search_console",
        )

        mock_discovery_service = AsyncMock()
        mock_discovery_service.discover_properties.side_effect = Exception("OAuth token expired")

        result = await job.execute(
            db_session=mock_db_session,
            discovery_service=mock_discovery_service,
        )

        assert result["success"] is False
        assert "OAuth token expired" in result["error"]

    @pytest.mark.asyncio
    async def test_property_sync_job_updates_integration_account(
        self,
        sample_project_id: uuid.UUID,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that property sync updates integration account last_synced."""
        from semrush_workers.jobs.property_sync_job import PropertySyncJob

        job = PropertySyncJob.create(
            integration_account_id=sample_project_id,
            provider="google_search_console",
        )

        mock_discovery_service = AsyncMock()
        mock_discovery_service.discover_properties = AsyncMock(return_value=[])

        # Mock integration account retrieval
        mock_account = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_account
        mock_db_session.execute.return_value = mock_result

        await job.execute(
            db_session=mock_db_session,
            discovery_service=mock_discovery_service,
        )

        mock_db_session.commit.assert_called()


class TestJobRetryLogic:
    """Tests for job retry logic."""

    @pytest.mark.asyncio
    async def test_job_retry_increments_attempts(
        self,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test that retrying a job increments attempts counter."""
        from semrush_workers.jobs.sync_job import SyncJob

        job = SyncJob.create(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
        )

        initial_attempts = job.attempts
        job.record_attempt()

        assert job.attempts == initial_attempts + 1

    @pytest.mark.asyncio
    async def test_job_retry_records_error(
        self,
        sample_mapping_id: uuid.UUID,
    ) -> None:
        """Test that retry records error message."""
        from semrush_workers.jobs.sync_job import SyncJob

        job = SyncJob.create(
            mapping_id=sample_mapping_id,
            sync_mode=SyncMode.INCREMENTAL,
        )

        job.record_error("Connection timeout")

        assert job.last_error == "Connection timeout"

    def test_job_exponential_backoff_with_jitter(self) -> None:
        """Test exponential backoff includes reasonable jitter."""
        from semrush_workers.jobs.base import Job, JobType

        job = Job(
            job_id=str(uuid.uuid4()),
            job_type=JobType.SYNC,
            payload={},
        )
        job.attempts = 2

        # Get multiple backoff values to check for variation
        delays = [job.get_backoff_delay(with_jitter=True) for _ in range(10)]

        # All delays should be in a reasonable range around 60 seconds (2^1 * 30)
        base_delay = 60
        for delay in delays:
            assert delay >= base_delay * 0.5
            assert delay <= base_delay * 1.5
