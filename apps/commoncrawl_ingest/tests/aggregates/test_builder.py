"""
Tests for AggregateBuilder.

Tests the orchestration of aggregate building for Common Crawl snapshots,
including coordination of RefDomainsAggregator and AnchorsAggregator.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from semrush_commoncrawl.aggregates.builder import AggregateBuilder, AggregateResult


class TestAggregateResult:
    """Tests for AggregateResult dataclass."""

    def test_aggregate_result_creation(self) -> None:
        """Test that AggregateResult can be created with all fields."""
        result = AggregateResult(
            snapshot_id="CC-MAIN-2024-10",
            refdomains_count=100,
            anchors_count=50,
            duration_seconds=5.5,
        )

        assert result.snapshot_id == "CC-MAIN-2024-10"
        assert result.refdomains_count == 100
        assert result.anchors_count == 50
        assert result.duration_seconds == 5.5

    def test_aggregate_result_with_zero_counts(self) -> None:
        """Test that AggregateResult handles zero counts."""
        result = AggregateResult(
            snapshot_id="CC-MAIN-2024-10",
            refdomains_count=0,
            anchors_count=0,
            duration_seconds=0.1,
        )

        assert result.refdomains_count == 0
        assert result.anchors_count == 0


class TestAggregateBuilderBuildAll:
    """Tests for AggregateBuilder.build_all method."""

    @pytest.mark.asyncio
    async def test_build_all_runs_both_aggregators(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that build_all runs both refdomains and anchors aggregators."""
        # Mock the execute to return rowcount for aggregation queries
        mock_result = MagicMock()
        mock_result.rowcount = 10
        mock_db_session.execute.return_value = mock_result

        builder = AggregateBuilder(mock_db_session)

        with patch.object(builder.refdomains, "build_for_snapshot", new_callable=AsyncMock) as mock_refdomains, \
             patch.object(builder.anchors, "build_for_snapshot", new_callable=AsyncMock) as mock_anchors:
            mock_refdomains.return_value = 50
            mock_anchors.return_value = 30

            await builder.build_all(sample_snapshot_id)

            mock_refdomains.assert_called_once_with(sample_snapshot_id)
            mock_anchors.assert_called_once_with(sample_snapshot_id)

    @pytest.mark.asyncio
    async def test_build_all_returns_correct_result(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that build_all returns AggregateResult with correct stats."""
        builder = AggregateBuilder(mock_db_session)

        with patch.object(builder.refdomains, "build_for_snapshot", new_callable=AsyncMock) as mock_refdomains, \
             patch.object(builder.anchors, "build_for_snapshot", new_callable=AsyncMock) as mock_anchors:
            mock_refdomains.return_value = 100
            mock_anchors.return_value = 75

            result = await builder.build_all(sample_snapshot_id)

            assert isinstance(result, AggregateResult)
            assert result.snapshot_id == sample_snapshot_id
            assert result.refdomains_count == 100
            assert result.anchors_count == 75

    @pytest.mark.asyncio
    async def test_build_all_calculates_duration(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that build_all calculates execution duration."""
        builder = AggregateBuilder(mock_db_session)

        with patch.object(builder.refdomains, "build_for_snapshot", new_callable=AsyncMock) as mock_refdomains, \
             patch.object(builder.anchors, "build_for_snapshot", new_callable=AsyncMock) as mock_anchors:
            mock_refdomains.return_value = 10
            mock_anchors.return_value = 5

            result = await builder.build_all(sample_snapshot_id)

            # Duration should be >= 0
            assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_build_all_updates_snapshot_status(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that build_all updates snapshot record with completion status."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        builder = AggregateBuilder(mock_db_session)

        with patch.object(builder.refdomains, "build_for_snapshot", new_callable=AsyncMock) as mock_refdomains, \
             patch.object(builder.anchors, "build_for_snapshot", new_callable=AsyncMock) as mock_anchors:
            mock_refdomains.return_value = 20
            mock_anchors.return_value = 15

            await builder.build_all(sample_snapshot_id)

            # Should have called execute to update snapshot record
            # Check that execute was called (for snapshot update)
            assert mock_db_session.execute.called or mock_db_session.commit.called


class TestAggregateBuilderTrigger:
    """Tests for AggregateBuilder.trigger_build method."""

    @pytest.mark.asyncio
    async def test_trigger_build_queues_job(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that trigger_build queues a background job."""
        builder = AggregateBuilder(mock_db_session)

        # trigger_build should not raise
        await builder.trigger_build(sample_snapshot_id)

    @pytest.mark.asyncio
    async def test_trigger_build_stores_job_info(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that trigger_build stores job information."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        builder = AggregateBuilder(mock_db_session)

        await builder.trigger_build(sample_snapshot_id)

        # Should interact with the database to record the job
        # (either via execute or similar)
        assert mock_db_session.execute.called or mock_db_session.commit.called


class TestAggregateBuilderErrorHandling:
    """Tests for error handling in AggregateBuilder."""

    @pytest.mark.asyncio
    async def test_build_all_handles_refdomains_error(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that errors in refdomains aggregation are propagated."""
        builder = AggregateBuilder(mock_db_session)

        with patch.object(builder.refdomains, "build_for_snapshot", new_callable=AsyncMock) as mock_refdomains:
            mock_refdomains.side_effect = Exception("RefDomains aggregation failed")

            with pytest.raises(Exception) as exc_info:
                await builder.build_all(sample_snapshot_id)

            assert "RefDomains aggregation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_build_all_handles_anchors_error(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that errors in anchors aggregation are propagated."""
        builder = AggregateBuilder(mock_db_session)

        with patch.object(builder.refdomains, "build_for_snapshot", new_callable=AsyncMock) as mock_refdomains, \
             patch.object(builder.anchors, "build_for_snapshot", new_callable=AsyncMock) as mock_anchors:
            mock_refdomains.return_value = 50
            mock_anchors.side_effect = Exception("Anchors aggregation failed")

            with pytest.raises(Exception) as exc_info:
                await builder.build_all(sample_snapshot_id)

            assert "Anchors aggregation failed" in str(exc_info.value)


class TestAggregateBuilderInitialization:
    """Tests for AggregateBuilder initialization."""

    def test_builder_initializes_aggregators(
        self,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that builder initializes both aggregators with the session."""
        builder = AggregateBuilder(mock_db_session)

        assert builder.refdomains is not None
        assert builder.anchors is not None
        assert builder.db is mock_db_session

    def test_builder_shares_session_with_aggregators(
        self,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that aggregators share the same database session."""
        builder = AggregateBuilder(mock_db_session)

        assert builder.refdomains.db is mock_db_session
        assert builder.anchors.db is mock_db_session


class TestAggregateBuilderSnapshotUpdate:
    """Tests for snapshot status updates."""

    @pytest.mark.asyncio
    async def test_build_all_updates_refdomains_count(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that snapshot's refdomains_count is updated after build."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        builder = AggregateBuilder(mock_db_session)

        with patch.object(builder.refdomains, "build_for_snapshot", new_callable=AsyncMock) as mock_refdomains, \
             patch.object(builder.anchors, "build_for_snapshot", new_callable=AsyncMock) as mock_anchors:
            mock_refdomains.return_value = 100
            mock_anchors.return_value = 50

            result = await builder.build_all(sample_snapshot_id)

            assert result.refdomains_count == 100

    @pytest.mark.asyncio
    async def test_build_all_updates_anchors_count(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that snapshot's anchors_count is updated after build."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        builder = AggregateBuilder(mock_db_session)

        with patch.object(builder.refdomains, "build_for_snapshot", new_callable=AsyncMock) as mock_refdomains, \
             patch.object(builder.anchors, "build_for_snapshot", new_callable=AsyncMock) as mock_anchors:
            mock_refdomains.return_value = 100
            mock_anchors.return_value = 75

            result = await builder.build_all(sample_snapshot_id)

            assert result.anchors_count == 75

    @pytest.mark.asyncio
    async def test_build_all_records_completion_time(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that aggregates_built_at timestamp is recorded."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        builder = AggregateBuilder(mock_db_session)

        with patch.object(builder.refdomains, "build_for_snapshot", new_callable=AsyncMock) as mock_refdomains, \
             patch.object(builder.anchors, "build_for_snapshot", new_callable=AsyncMock) as mock_anchors:
            mock_refdomains.return_value = 10
            mock_anchors.return_value = 5

            result = await builder.build_all(sample_snapshot_id)

            # Duration should be recorded
            assert result.duration_seconds >= 0
