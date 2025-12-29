"""
Tests for the Common Crawl router.

Tests cover:
- GET /commoncrawl/snapshots - List all snapshots
- POST /commoncrawl/snapshots - Register a new snapshot
- POST /commoncrawl/ingest - Trigger ingestion
- GET /commoncrawl/snapshots/{snapshot_id} - Get snapshot details
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def test_snapshot_id() -> str:
    """Test Common Crawl snapshot ID."""
    return "CC-MAIN-2025-05"


@pytest.fixture
def test_snapshot_id_2() -> str:
    """Second test snapshot ID."""
    return "CC-MAIN-2025-06"


@pytest.fixture
def sample_snapshot() -> MagicMock:
    """Create a sample snapshot object."""
    mock = MagicMock()
    mock.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    mock.snapshot_id = "CC-MAIN-2025-05"
    mock.status = "known"
    mock.date_range_start = date(2025, 1, 1)
    mock.date_range_end = date(2025, 1, 31)
    mock.total_records = 1000000
    mock.edges_ingested = 0
    mock.ingestion_started_at = None
    mock.ingestion_completed_at = None
    mock.error_message = None
    mock.notes = "Test snapshot"
    mock.created_at = datetime(2025, 1, 15, tzinfo=UTC)
    mock.spec = {}
    return mock


@pytest.fixture
def sample_snapshot_ingesting() -> MagicMock:
    """Create a snapshot in ingesting status."""
    mock = MagicMock()
    mock.id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    mock.snapshot_id = "CC-MAIN-2025-06"
    mock.status = "ingesting"
    mock.date_range_start = date(2025, 2, 1)
    mock.date_range_end = date(2025, 2, 28)
    mock.total_records = 2000000
    mock.edges_ingested = 500000
    mock.ingestion_started_at = datetime(2025, 2, 20, tzinfo=UTC)
    mock.ingestion_completed_at = None
    mock.error_message = None
    mock.notes = None
    mock.created_at = datetime(2025, 2, 15, tzinfo=UTC)
    mock.spec = {}
    return mock


@pytest.fixture
def sample_snapshot_ingested() -> MagicMock:
    """Create a snapshot in ingested status."""
    mock = MagicMock()
    mock.id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    mock.snapshot_id = "CC-MAIN-2025-04"
    mock.status = "ingested"
    mock.date_range_start = date(2024, 12, 1)
    mock.date_range_end = date(2024, 12, 31)
    mock.total_records = 1500000
    mock.edges_ingested = 1500000
    mock.ingestion_started_at = datetime(2025, 1, 5, tzinfo=UTC)
    mock.ingestion_completed_at = datetime(2025, 1, 6, tzinfo=UTC)
    mock.error_message = None
    mock.notes = "Successfully ingested"
    mock.created_at = datetime(2025, 1, 1, tzinfo=UTC)
    mock.spec = {}
    return mock


@pytest.fixture
def sample_snapshot_failed() -> MagicMock:
    """Create a snapshot in failed status."""
    mock = MagicMock()
    mock.id = uuid.UUID("44444444-4444-4444-4444-444444444444")
    mock.snapshot_id = "CC-MAIN-2025-03"
    mock.status = "failed"
    mock.date_range_start = date(2024, 11, 1)
    mock.date_range_end = date(2024, 11, 30)
    mock.total_records = 1200000
    mock.edges_ingested = 100000
    mock.ingestion_started_at = datetime(2024, 12, 1, tzinfo=UTC)
    mock.ingestion_completed_at = None
    mock.error_message = "Connection timeout"
    mock.notes = None
    mock.created_at = datetime(2024, 11, 15, tzinfo=UTC)
    mock.spec = {}
    return mock


class TestListSnapshots:
    """Tests for GET /commoncrawl/snapshots."""

    @pytest.mark.asyncio
    async def test_list_snapshots_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot,
        sample_snapshot_ingesting,
    ):
        """Successfully list all snapshots."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            sample_snapshot,
            sample_snapshot_ingesting,
        ]

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/commoncrawl/snapshots",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert data["items"][0]["snapshot_id"] == "CC-MAIN-2025-05"
        assert data["items"][0]["status"] == "known"
        assert data["items"][1]["snapshot_id"] == "CC-MAIN-2025-06"

    @pytest.mark.asyncio
    async def test_list_snapshots_with_status_filter(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot,
    ):
        """Filter snapshots by status."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_snapshot]

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/commoncrawl/snapshots?status=known",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "known"

    @pytest.mark.asyncio
    async def test_list_snapshots_with_limit(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot,
    ):
        """Limit parameter is applied."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_snapshot]

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/commoncrawl/snapshots?limit=1",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_list_snapshots_limit_max_100(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Limit cannot exceed 100."""
        response = await client.get(
            "/commoncrawl/snapshots?limit=150",
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_snapshots_empty(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Return empty list when no snapshots exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/commoncrawl/snapshots",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_snapshots_unauthorized(
        self,
        client,
    ):
        """Returns 401 without authentication."""
        response = await client.get("/commoncrawl/snapshots")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_snapshots_invalid_status(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 422 with invalid status value."""
        response = await client.get(
            "/commoncrawl/snapshots?status=invalid_status",
            headers=auth_headers,
        )

        assert response.status_code == 422


class TestCreateSnapshot:
    """Tests for POST /commoncrawl/snapshots."""

    @pytest.mark.asyncio
    async def test_create_snapshot_success(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Successfully create a new snapshot."""
        # Mock no existing snapshot
        mock_check_result = MagicMock()
        mock_check_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_check_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        response = await client.post(
            "/commoncrawl/snapshots",
            headers=auth_headers,
            json={
                "snapshot_id": "CC-MAIN-2025-07",
                "date_range_start": "2025-03-01",
                "date_range_end": "2025-03-31",
                "notes": "New snapshot",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["snapshot_id"] == "CC-MAIN-2025-07"
        assert data["status"] == "known"

    @pytest.mark.asyncio
    async def test_create_snapshot_minimal(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Create snapshot with only required fields."""
        mock_check_result = MagicMock()
        mock_check_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_check_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        response = await client.post(
            "/commoncrawl/snapshots",
            headers=auth_headers,
            json={
                "snapshot_id": "CC-MAIN-2025-08",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["snapshot_id"] == "CC-MAIN-2025-08"
        assert data["status"] == "known"

    @pytest.mark.asyncio
    async def test_create_snapshot_duplicate(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot,
    ):
        """Returns 409 when snapshot already exists."""
        mock_check_result = MagicMock()
        mock_check_result.scalar_one_or_none.return_value = sample_snapshot

        mock_db_session.execute = AsyncMock(return_value=mock_check_result)

        response = await client.post(
            "/commoncrawl/snapshots",
            headers=auth_headers,
            json={
                "snapshot_id": "CC-MAIN-2025-05",  # Same as sample_snapshot
            },
        )

        assert response.status_code == 409
        data = response.json()
        assert "already exists" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_create_snapshot_missing_snapshot_id(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 422 when snapshot_id is missing."""
        response = await client.post(
            "/commoncrawl/snapshots",
            headers=auth_headers,
            json={
                "notes": "Missing snapshot_id",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_snapshot_invalid_date_format(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 422 when date format is invalid."""
        response = await client.post(
            "/commoncrawl/snapshots",
            headers=auth_headers,
            json={
                "snapshot_id": "CC-MAIN-2025-07",
                "date_range_start": "not-a-date",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_snapshot_unauthorized(
        self,
        client,
    ):
        """Returns 401 without authentication."""
        response = await client.post(
            "/commoncrawl/snapshots",
            json={
                "snapshot_id": "CC-MAIN-2025-07",
            },
        )
        assert response.status_code == 401


class TestTriggerIngest:
    """Tests for POST /commoncrawl/ingest."""

    @pytest.mark.asyncio
    async def test_trigger_ingest_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot,
    ):
        """Successfully trigger ingestion for a known snapshot."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snapshot

        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()

        response = await client.post(
            "/commoncrawl/ingest",
            headers=auth_headers,
            json={
                "snapshot_id": "CC-MAIN-2025-05",
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["snapshot_id"] == "CC-MAIN-2025-05"
        assert data["status"] == "ingesting"

    @pytest.mark.asyncio
    async def test_trigger_ingest_with_subset(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot,
    ):
        """Trigger ingestion with subset parameters."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snapshot

        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()

        response = await client.post(
            "/commoncrawl/ingest",
            headers=auth_headers,
            json={
                "snapshot_id": "CC-MAIN-2025-05",
                "subset": {
                    "target_domains": ["example.com", "test.org"],
                    "sample_rate": 0.5,
                    "max_edges": 10000,
                },
                "build_aggregates": True,
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["snapshot_id"] == "CC-MAIN-2025-05"

    @pytest.mark.asyncio
    async def test_trigger_ingest_from_failed_status(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot_failed,
    ):
        """Can retry ingestion for a failed snapshot."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snapshot_failed

        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()

        response = await client.post(
            "/commoncrawl/ingest",
            headers=auth_headers,
            json={
                "snapshot_id": "CC-MAIN-2025-03",
            },
        )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_trigger_ingest_not_found(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 404 when snapshot does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/commoncrawl/ingest",
            headers=auth_headers,
            json={
                "snapshot_id": "CC-MAIN-NONEXISTENT",
            },
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_ingest_already_ingesting(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot_ingesting,
    ):
        """Returns 409 when snapshot is already being ingested."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snapshot_ingesting

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/commoncrawl/ingest",
            headers=auth_headers,
            json={
                "snapshot_id": "CC-MAIN-2025-06",
            },
        )

        assert response.status_code == 409
        data = response.json()
        assert "ingesting" in data["message"].lower() or "progress" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_trigger_ingest_already_ingested(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot_ingested,
    ):
        """Returns 409 when snapshot is already fully ingested."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snapshot_ingested

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/commoncrawl/ingest",
            headers=auth_headers,
            json={
                "snapshot_id": "CC-MAIN-2025-04",
            },
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_trigger_ingest_invalid_sample_rate(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 422 when sample_rate is out of range."""
        response = await client.post(
            "/commoncrawl/ingest",
            headers=auth_headers,
            json={
                "snapshot_id": "CC-MAIN-2025-05",
                "subset": {
                    "sample_rate": 1.5,  # Invalid: > 1.0
                },
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_trigger_ingest_invalid_sample_rate_negative(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 422 when sample_rate is negative."""
        response = await client.post(
            "/commoncrawl/ingest",
            headers=auth_headers,
            json={
                "snapshot_id": "CC-MAIN-2025-05",
                "subset": {
                    "sample_rate": -0.1,  # Invalid: < 0.0
                },
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_trigger_ingest_unauthorized(
        self,
        client,
    ):
        """Returns 401 without authentication."""
        response = await client.post(
            "/commoncrawl/ingest",
            json={
                "snapshot_id": "CC-MAIN-2025-05",
            },
        )
        assert response.status_code == 401


class TestGetSnapshotDetails:
    """Tests for GET /commoncrawl/snapshots/{snapshot_id}."""

    @pytest.mark.asyncio
    async def test_get_snapshot_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot,
    ):
        """Successfully get snapshot details."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snapshot

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/commoncrawl/snapshots/CC-MAIN-2025-05",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["snapshot_id"] == "CC-MAIN-2025-05"
        assert data["status"] == "known"
        assert data["date_range_start"] == "2025-01-01"
        assert data["date_range_end"] == "2025-01-31"
        assert data["total_records"] == 1000000
        assert data["edges_ingested"] == 0
        assert data["notes"] == "Test snapshot"

    @pytest.mark.asyncio
    async def test_get_snapshot_ingesting(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot_ingesting,
    ):
        """Get details of a snapshot in progress."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snapshot_ingesting

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/commoncrawl/snapshots/CC-MAIN-2025-06",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["snapshot_id"] == "CC-MAIN-2025-06"
        assert data["status"] == "ingesting"
        assert data["edges_ingested"] == 500000
        assert data["ingestion_started_at"] is not None

    @pytest.mark.asyncio
    async def test_get_snapshot_completed(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot_ingested,
    ):
        """Get details of a completed snapshot."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snapshot_ingested

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/commoncrawl/snapshots/CC-MAIN-2025-04",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ingested"
        assert data["ingestion_completed_at"] is not None
        assert data["edges_ingested"] == 1500000

    @pytest.mark.asyncio
    async def test_get_snapshot_failed(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshot_failed,
    ):
        """Get details of a failed snapshot."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_snapshot_failed

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/commoncrawl/snapshots/CC-MAIN-2025-03",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "Connection timeout"

    @pytest.mark.asyncio
    async def test_get_snapshot_not_found(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 404 when snapshot does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/commoncrawl/snapshots/CC-MAIN-NONEXISTENT",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_snapshot_unauthorized(
        self,
        client,
    ):
        """Returns 401 without authentication."""
        response = await client.get("/commoncrawl/snapshots/CC-MAIN-2025-05")
        assert response.status_code == 401
