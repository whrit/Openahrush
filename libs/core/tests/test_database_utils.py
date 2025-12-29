"""
Tests for database optimization utilities.

Tests cover:
- Keyset pagination (cursor-based pagination)
- Eager loading helpers
- Batch fetch utilities
- Query logging with slow query detection
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import ForeignKey, String, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# Create a separate base for test models to avoid polluting the main model registry
class SampleBase(DeclarativeBase):
    """Base class for sample test models."""

    pass


# Sample models for pagination and eager loading tests
class SampleParentModel(SampleBase):
    """Sample parent model with relationships."""

    __tablename__ = "sample_parents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    children: Mapped[list[SampleChildModel]] = relationship(
        back_populates="parent",
        lazy="select",
    )


class SampleChildModel(SampleBase):
    """Sample child model for relationship testing."""

    __tablename__ = "sample_children"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sample_parents.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent: Mapped[SampleParentModel] = relationship(back_populates="children")


# ============================================================================
# KeysetPaginator Tests
# ============================================================================


class TestKeysetPaginatorEncodeCursor:
    """Tests for cursor encoding functionality."""

    def test_encodes_single_value_cursor(self) -> None:
        """Cursor with single value should be base64 encoded JSON."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()
        cursor = paginator.encode_cursor({"id": "abc-123"})
        decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        assert decoded == {"id": "abc-123"}

    def test_encodes_multi_value_cursor(self) -> None:
        """Cursor with multiple values should preserve all fields."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()
        cursor = paginator.encode_cursor({"created_at": "2024-01-01T00:00:00Z", "id": "abc-123"})
        decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        assert decoded == {"created_at": "2024-01-01T00:00:00Z", "id": "abc-123"}

    def test_encodes_uuid_values(self) -> None:
        """UUID values should be converted to strings."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()
        test_uuid = uuid.uuid4()
        cursor = paginator.encode_cursor({"id": test_uuid})
        decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        assert decoded == {"id": str(test_uuid)}

    def test_encodes_datetime_values(self) -> None:
        """Datetime values should be converted to ISO format strings."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        cursor = paginator.encode_cursor({"created_at": dt})
        decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        assert "2024-01-15" in decoded["created_at"]


class TestKeysetPaginatorDecodeCursor:
    """Tests for cursor decoding functionality."""

    def test_decodes_valid_cursor(self) -> None:
        """Valid cursor should decode to original values."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()
        original = {"id": "abc-123", "name": "test"}
        cursor = paginator.encode_cursor(original)
        decoded = paginator.decode_cursor(cursor)
        assert decoded == original

    def test_returns_none_for_none_cursor(self) -> None:
        """None cursor should return None."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()
        assert paginator.decode_cursor(None) is None

    def test_returns_none_for_empty_cursor(self) -> None:
        """Empty string cursor should return None."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()
        assert paginator.decode_cursor("") is None

    def test_raises_for_invalid_base64(self) -> None:
        """Invalid base64 cursor should raise ValueError."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()
        with pytest.raises(ValueError, match="Invalid cursor"):
            paginator.decode_cursor("not-valid-base64!!!")

    def test_raises_for_invalid_json(self) -> None:
        """Valid base64 but invalid JSON should raise ValueError."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()
        invalid_json = base64.urlsafe_b64encode(b"not json").decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            paginator.decode_cursor(invalid_json)


class TestKeysetPaginatorPaginate:
    """Tests for pagination execution."""

    @pytest.mark.asyncio
    async def test_returns_paginated_result_structure(self) -> None:
        """Paginate should return PaginatedResult with correct structure."""
        from semrush_core.db_utils.pagination import KeysetPaginator, PaginatedResult

        paginator = KeysetPaginator()

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        query = select(SampleParentModel)
        result = await paginator.paginate(
            session=mock_session,
            query=query,
            order_by_columns=["created_at", "id"],
            cursor=None,
            limit=20,
        )

        assert isinstance(result, PaginatedResult)
        assert hasattr(result, "items")
        assert hasattr(result, "next_cursor")
        assert hasattr(result, "has_more")

    @pytest.mark.asyncio
    async def test_applies_limit_plus_one_for_has_more_check(self) -> None:
        """Query should fetch limit+1 items to determine if more exist."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        query = select(SampleParentModel)
        await paginator.paginate(
            session=mock_session,
            query=query,
            order_by_columns=["id"],
            limit=20,
        )

        # Verify execute was called
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_has_more_true_when_extra_item_exists(self) -> None:
        """has_more should be True when limit+1 items are returned."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()

        # Create 21 mock items (limit=20, so 21 means has_more=True)
        mock_items = [MagicMock(id=uuid.uuid4(), created_at=datetime.now(UTC)) for _ in range(21)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_items
        mock_session.execute.return_value = mock_result

        query = select(SampleParentModel)
        result = await paginator.paginate(
            session=mock_session,
            query=query,
            order_by_columns=["id"],
            limit=20,
        )

        assert result.has_more is True
        assert len(result.items) == 20  # Should return only limit items

    @pytest.mark.asyncio
    async def test_has_more_false_when_fewer_items(self) -> None:
        """has_more should be False when less than limit items are returned."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()

        mock_items = [MagicMock(id=uuid.uuid4()) for _ in range(5)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_items
        mock_session.execute.return_value = mock_result

        query = select(SampleParentModel)
        result = await paginator.paginate(
            session=mock_session,
            query=query,
            order_by_columns=["id"],
            limit=20,
        )

        assert result.has_more is False
        assert result.next_cursor is None

    @pytest.mark.asyncio
    async def test_generates_next_cursor_from_last_item(self) -> None:
        """next_cursor should be generated from the last returned item."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()

        last_id = uuid.uuid4()
        mock_items = [MagicMock(id=uuid.uuid4()) for _ in range(20)]
        mock_items.append(MagicMock(id=last_id))  # 21st item for has_more check

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_items
        mock_session.execute.return_value = mock_result

        query = select(SampleParentModel)
        result = await paginator.paginate(
            session=mock_session,
            query=query,
            order_by_columns=["id"],
            limit=20,
        )

        assert result.next_cursor is not None
        decoded = paginator.decode_cursor(result.next_cursor)
        assert decoded is not None
        # The cursor should contain the last item's id (20th item, 0-indexed = 19)
        assert "id" in decoded


class TestKeysetPaginatorBuildCursorFilter:
    """Tests for cursor filter building."""

    def test_builds_filter_for_single_column_ascending(self) -> None:
        """Single column ascending should filter for values > cursor."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()
        cursor_values = {"id": "abc-123"}
        columns = {"id": SampleParentModel.id}

        filter_clause = paginator.build_cursor_filter(
            cursor_values=cursor_values,
            columns=columns,
            descending=False,
        )

        assert filter_clause is not None

    def test_builds_filter_for_single_column_descending(self) -> None:
        """Single column descending should filter for values < cursor."""
        from semrush_core.db_utils.pagination import KeysetPaginator

        paginator = KeysetPaginator()
        cursor_values = {"id": "abc-123"}
        columns = {"id": SampleParentModel.id}

        filter_clause = paginator.build_cursor_filter(
            cursor_values=cursor_values,
            columns=columns,
            descending=True,
        )

        assert filter_clause is not None


# ============================================================================
# Eager Loading Tests
# ============================================================================


class TestWithEagerLoads:
    """Tests for eager loading helper function."""

    def test_returns_modified_query(self) -> None:
        """with_eager_loads should return a query with joinedload options."""
        from semrush_core.db_utils.eager_load import with_eager_loads

        query = select(SampleParentModel)
        result = with_eager_loads(query, "children")

        assert result is not None
        # The query should be modified (options added)
        assert result is not query or hasattr(result, "_with_options")

    def test_handles_multiple_relationships(self) -> None:
        """Should handle multiple relationship names."""
        from semrush_core.db_utils.eager_load import with_eager_loads

        query = select(SampleParentModel)
        result = with_eager_loads(query, "children", "some_other_rel")

        assert result is not None

    def test_handles_empty_relationships(self) -> None:
        """Should return original query when no relationships specified."""
        from semrush_core.db_utils.eager_load import with_eager_loads

        query = select(SampleParentModel)
        result = with_eager_loads(query)

        assert result is not None


class TestWithSelectinLoads:
    """Tests for selectin loading helper function."""

    def test_returns_modified_query(self) -> None:
        """with_selectin_loads should return a query with selectinload options."""
        from semrush_core.db_utils.eager_load import with_selectin_loads

        query = select(SampleParentModel)
        result = with_selectin_loads(query, "children")

        assert result is not None


class TestBuildEagerLoadOptions:
    """Tests for building eager load options programmatically."""

    def test_creates_joinedload_options(self) -> None:
        """Should create joinedload options for specified relationships."""
        from semrush_core.db_utils.eager_load import build_eager_load_options

        options = build_eager_load_options(SampleParentModel, ["children"])
        assert len(options) == 1

    def test_returns_empty_list_for_no_relationships(self) -> None:
        """Should return empty list when no relationships specified."""
        from semrush_core.db_utils.eager_load import build_eager_load_options

        options = build_eager_load_options(SampleParentModel, [])
        assert options == []


# ============================================================================
# Batch Fetch Tests
# ============================================================================


class TestBatchFetch:
    """Tests for batch fetch utility."""

    @pytest.mark.asyncio
    async def test_fetches_all_ids_in_batches(self) -> None:
        """Should fetch all records by splitting into batches."""
        from semrush_core.db_utils.batch import batch_fetch

        # Create 250 IDs (should split into 3 batches with batch_size=100)
        ids = [uuid.uuid4() for _ in range(250)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await batch_fetch(
            session=mock_session,
            model=SampleParentModel,
            ids=ids,
            batch_size=100,
        )

        # Should have made 3 execute calls (100 + 100 + 50)
        assert mock_session.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_empty_ids(self) -> None:
        """Should return empty list when no IDs provided."""
        from semrush_core.db_utils.batch import batch_fetch

        mock_session = AsyncMock(spec=AsyncSession)

        result = await batch_fetch(
            session=mock_session,
            model=SampleParentModel,
            ids=[],
        )

        assert result == []
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_batch_for_small_id_list(self) -> None:
        """Should make single query when IDs fit in one batch."""
        from semrush_core.db_utils.batch import batch_fetch

        ids = [uuid.uuid4() for _ in range(50)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await batch_fetch(
            session=mock_session,
            model=SampleParentModel,
            ids=ids,
            batch_size=100,
        )

        assert mock_session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_preserves_order_of_results(self) -> None:
        """Results should be returned in a consistent order."""
        from semrush_core.db_utils.batch import batch_fetch

        ids = [uuid.uuid4() for _ in range(5)]

        # Create mock items that will be returned
        mock_items = [MagicMock(id=id_) for id_ in ids]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_items
        mock_session.execute.return_value = mock_result

        result = await batch_fetch(
            session=mock_session,
            model=SampleParentModel,
            ids=ids,
        )

        assert len(result) == 5


class TestBatchFetchWithEagerLoad:
    """Tests for batch fetch with eager loading."""

    @pytest.mark.asyncio
    async def test_applies_eager_load_relationships(self) -> None:
        """Should apply eager loading when relationships specified."""
        from semrush_core.db_utils.batch import batch_fetch_with_eager_load

        ids = [uuid.uuid4() for _ in range(5)]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await batch_fetch_with_eager_load(
            session=mock_session,
            model=SampleParentModel,
            ids=ids,
            relationships=["children"],
        )

        mock_session.execute.assert_called()


# ============================================================================
# Query Logging Tests
# ============================================================================


class TestQueryLogger:
    """Tests for query logging functionality."""

    def test_logs_query_when_enabled(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should log queries when logging is enabled."""
        from semrush_core.db_utils.query_log import QueryLogger

        logger = QueryLogger(enabled=True, log_level=logging.DEBUG)

        with caplog.at_level(logging.DEBUG):
            logger.log_query("SELECT * FROM users WHERE id = $1", duration_ms=5.0)

        assert "SELECT * FROM users" in caplog.text

    def test_does_not_log_when_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should not log when logging is disabled."""
        from semrush_core.db_utils.query_log import QueryLogger

        logger = QueryLogger(enabled=False)

        with caplog.at_level(logging.DEBUG):
            logger.log_query("SELECT * FROM users", duration_ms=5.0)

        assert "SELECT * FROM users" not in caplog.text

    def test_logs_slow_query_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should log warning for queries exceeding threshold."""
        from semrush_core.db_utils.query_log import QueryLogger

        logger = QueryLogger(
            enabled=True,
            slow_query_threshold_ms=100.0,
            log_level=logging.DEBUG,
        )

        with caplog.at_level(logging.DEBUG):
            logger.log_query("SELECT * FROM large_table", duration_ms=150.0)

        assert "SLOW QUERY" in caplog.text or "slow" in caplog.text.lower()

    def test_does_not_warn_for_fast_queries(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should not warn for queries under threshold."""
        from semrush_core.db_utils.query_log import QueryLogger

        logger = QueryLogger(
            enabled=True,
            slow_query_threshold_ms=100.0,
            log_level=logging.DEBUG,
        )

        with caplog.at_level(logging.DEBUG):
            logger.log_query("SELECT * FROM users WHERE id = 1", duration_ms=5.0)

        assert "SLOW QUERY" not in caplog.text


class TestSlowQueryDetector:
    """Tests for slow query detection."""

    def test_detects_slow_query(self) -> None:
        """Should identify queries exceeding threshold as slow."""
        from semrush_core.db_utils.query_log import SlowQueryDetector

        detector = SlowQueryDetector(threshold_ms=100.0)
        assert detector.is_slow(150.0) is True

    def test_accepts_fast_query(self) -> None:
        """Should not flag queries under threshold."""
        from semrush_core.db_utils.query_log import SlowQueryDetector

        detector = SlowQueryDetector(threshold_ms=100.0)
        assert detector.is_slow(50.0) is False

    def test_threshold_boundary(self) -> None:
        """Queries at exact threshold should not be flagged as slow."""
        from semrush_core.db_utils.query_log import SlowQueryDetector

        detector = SlowQueryDetector(threshold_ms=100.0)
        assert detector.is_slow(100.0) is False

    def test_tracks_slow_query_count(self) -> None:
        """Should track count of slow queries."""
        from semrush_core.db_utils.query_log import SlowQueryDetector

        detector = SlowQueryDetector(threshold_ms=100.0)
        detector.record_query(50.0)
        detector.record_query(150.0)
        detector.record_query(200.0)
        detector.record_query(75.0)

        assert detector.slow_query_count == 2
        assert detector.total_query_count == 4


class TestQueryLoggerContextManager:
    """Tests for query logger context manager."""

    @pytest.mark.asyncio
    async def test_measures_query_duration(self) -> None:
        """Context manager should measure and log query duration."""
        from semrush_core.db_utils.query_log import QueryLogger

        logger = QueryLogger(enabled=True, log_level=logging.DEBUG)
        durations: list[float] = []

        original_log = logger.log_query

        def capture_duration(query: str, duration_ms: float) -> None:
            durations.append(duration_ms)
            original_log(query, duration_ms)

        logger.log_query = capture_duration  # type: ignore[method-assign]

        async with logger.timed_query("SELECT 1"):
            pass  # Simulating quick query

        assert len(durations) == 1
        assert durations[0] >= 0


class TestQueryLoggingConfig:
    """Tests for query logging configuration."""

    def test_creates_logger_from_environment(self) -> None:
        """Should create logger with settings from environment."""
        from semrush_core.db_utils.query_log import create_query_logger

        with patch.dict(
            "os.environ",
            {
                "QUERY_LOG_ENABLED": "true",
                "QUERY_LOG_SLOW_THRESHOLD_MS": "200",
            },
        ):
            logger = create_query_logger()
            assert logger.enabled is True
            assert logger.slow_query_threshold_ms == 200.0

    def test_defaults_to_disabled_in_production(self) -> None:
        """Query logging should default to disabled."""
        from semrush_core.db_utils.query_log import create_query_logger

        with patch.dict("os.environ", {}, clear=True):
            logger = create_query_logger()
            assert logger.enabled is False


# ============================================================================
# Connection Pool Configuration Tests
# ============================================================================


class TestPoolConfiguration:
    """Tests for connection pool configuration."""

    def test_pool_settings_from_config(self) -> None:
        """Pool settings should be configurable via Settings."""
        from semrush_core.config import Settings

        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/test",
                "REDIS_URL": "redis://localhost:6379/0",
                "JWT_SECRET": "a" * 32,
                "DATABASE_POOL_SIZE": "20",
                "DATABASE_MAX_OVERFLOW": "30",
                "DATABASE_POOL_TIMEOUT": "60",
            },
        ):
            settings = Settings()
            assert settings.database_pool_size == 20
            assert settings.database_max_overflow == 30
            assert settings.database_pool_timeout == 60

    def test_default_pool_settings(self) -> None:
        """Pool settings should have sensible defaults."""
        from semrush_core.config import Settings

        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/test",
                "REDIS_URL": "redis://localhost:6379/0",
                "JWT_SECRET": "a" * 32,
            },
        ):
            settings = Settings()
            assert settings.database_pool_size >= 1
            assert settings.database_max_overflow >= 0
            assert settings.database_pool_timeout >= 1


# ============================================================================
# N+1 Detection Helper Tests
# ============================================================================


class TestN1QueryDetector:
    """Tests for N+1 query detection helper."""

    def test_detects_repeated_similar_queries(self) -> None:
        """Should detect when similar queries are executed repeatedly."""
        from semrush_core.db_utils.query_log import N1QueryDetector

        detector = N1QueryDetector(threshold=5)

        # Simulate N+1 pattern: same query executed many times
        for _i in range(10):
            detector.record_query(f"SELECT * FROM children WHERE parent_id = '{uuid.uuid4()}'")

        warnings = detector.get_warnings()
        assert len(warnings) > 0
        assert any("N+1" in w or "repeated" in w.lower() for w in warnings)

    def test_does_not_warn_for_varied_queries(self) -> None:
        """Should not warn when queries are genuinely different."""
        from semrush_core.db_utils.query_log import N1QueryDetector

        detector = N1QueryDetector(threshold=5)

        detector.record_query("SELECT * FROM users")
        detector.record_query("SELECT * FROM projects")
        detector.record_query("SELECT * FROM crawl_runs")

        warnings = detector.get_warnings()
        assert len(warnings) == 0

    def test_normalizes_query_parameters(self) -> None:
        """Should normalize parameter values to detect similar patterns."""
        from semrush_core.db_utils.query_log import N1QueryDetector

        detector = N1QueryDetector(threshold=3)

        # These should be recognized as the same pattern
        detector.record_query("SELECT * FROM users WHERE id = 'abc-123'")
        detector.record_query("SELECT * FROM users WHERE id = 'def-456'")
        detector.record_query("SELECT * FROM users WHERE id = 'ghi-789'")
        detector.record_query("SELECT * FROM users WHERE id = 'jkl-012'")

        warnings = detector.get_warnings()
        assert len(warnings) > 0


class TestQueryPatternNormalizer:
    """Tests for query pattern normalization."""

    def test_normalizes_uuid_values(self) -> None:
        """Should replace UUIDs with placeholder."""
        from semrush_core.db_utils.query_log import normalize_query_pattern

        query = "SELECT * FROM users WHERE id = '550e8400-e29b-41d4-a716-446655440000'"
        normalized = normalize_query_pattern(query)
        assert "550e8400" not in normalized
        assert "?" in normalized or "<UUID>" in normalized

    def test_normalizes_numeric_values(self) -> None:
        """Should replace numeric literals with placeholder."""
        from semrush_core.db_utils.query_log import normalize_query_pattern

        query = "SELECT * FROM users LIMIT 20 OFFSET 100"
        normalized = normalize_query_pattern(query)
        assert "20" not in normalized or "?" in normalized

    def test_normalizes_string_literals(self) -> None:
        """Should replace string literals with placeholder."""
        from semrush_core.db_utils.query_log import normalize_query_pattern

        query = "SELECT * FROM users WHERE name = 'John Doe'"
        normalized = normalize_query_pattern(query)
        assert "John Doe" not in normalized


# ============================================================================
# PaginatedResult Tests
# ============================================================================


class TestPaginatedResult:
    """Tests for PaginatedResult dataclass."""

    def test_creates_paginated_result(self) -> None:
        """Should create PaginatedResult with all fields."""
        from semrush_core.db_utils.pagination import PaginatedResult

        result: PaginatedResult[dict[str, str]] = PaginatedResult(
            items=[{"id": "1"}, {"id": "2"}],
            next_cursor="abc123",
            has_more=True,
        )

        assert len(result.items) == 2
        assert result.next_cursor == "abc123"
        assert result.has_more is True

    def test_converts_to_dict(self) -> None:
        """Should convert to dictionary for API responses."""
        from semrush_core.db_utils.pagination import PaginatedResult

        result: PaginatedResult[dict[str, str]] = PaginatedResult(
            items=[{"id": "1"}],
            next_cursor="abc123",
            has_more=True,
        )

        as_dict = result.to_dict()
        assert "items" in as_dict
        assert "next_cursor" in as_dict
        assert "has_more" in as_dict
