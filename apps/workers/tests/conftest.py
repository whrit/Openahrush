"""
Pytest fixtures for worker tests.

Uses fakeredis for mocking Redis and provides common test utilities.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from semrush_core.models.sync_run import SyncMode, SyncStatus


@pytest.fixture
def fake_redis() -> fakeredis.aioredis.FakeRedis:
    """Create a fake Redis instance for testing."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest_asyncio.fixture
async def async_fake_redis() -> AsyncGenerator[Redis, None]:
    """Create an async fake Redis instance for testing."""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


@pytest.fixture
def sample_mapping_id() -> uuid.UUID:
    """Create a sample mapping ID for testing."""
    return uuid.uuid4()


@pytest.fixture
def sample_project_id() -> uuid.UUID:
    """Create a sample project ID for testing."""
    return uuid.uuid4()


@pytest.fixture
def sample_sync_run(sample_mapping_id: uuid.UUID) -> dict[str, Any]:
    """Create sample sync run data for testing."""
    return {
        "id": uuid.uuid4(),
        "integration_mapping_id": sample_mapping_id,
        "provider": "google_search_console",
        "property_id": "sc-domain:example.com",
        "mode": SyncMode.INCREMENTAL.value,
        "status": SyncStatus.QUEUED.value,
        "date_range_start": date(2024, 1, 1),
        "date_range_end": date(2024, 1, 31),
        "records_written": 0,
        "error_message": None,
        "started_at": None,
        "completed_at": None,
        "created_at": datetime.now(UTC),
    }


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_data_sync_service() -> AsyncMock:
    """Create a mock data sync service."""
    service = AsyncMock()
    service.sync_data = AsyncMock(return_value={"records_written": 100})
    return service
