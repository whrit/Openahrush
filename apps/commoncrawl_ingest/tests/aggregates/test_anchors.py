"""
Tests for AnchorsAggregator.

Tests the aggregation of anchor text from raw edges,
including anchor normalization (trimming) and count aggregation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from semrush_commoncrawl.aggregates.anchors import AnchorsAggregator


class TestAnchorsAggregatorBuildForSnapshot:
    """Tests for AnchorsAggregator.build_for_snapshot method."""

    @pytest.mark.asyncio
    async def test_build_for_snapshot_creates_aggregates(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that build_for_snapshot creates correct anchor aggregates."""
        mock_result = MagicMock()
        mock_result.rowcount = 3  # 3 unique anchors (excluding empty/null)
        mock_db_session.execute.return_value = mock_result

        aggregator = AnchorsAggregator(mock_db_session)
        count = await aggregator.build_for_snapshot(sample_snapshot_id)

        assert mock_db_session.execute.called
        assert count == 3

    @pytest.mark.asyncio
    async def test_build_for_snapshot_uses_correct_sql(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that build_for_snapshot uses INSERT ... ON CONFLICT pattern."""
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_db_session.execute.return_value = mock_result

        aggregator = AnchorsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        call_args = mock_db_session.execute.call_args
        assert call_args is not None

        sql_text = str(call_args[0][0])
        assert "commoncrawl_anchors" in sql_text.lower() or "INSERT" in sql_text

    @pytest.mark.asyncio
    async def test_build_for_snapshot_groups_by_domain_anchor(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that aggregation groups by (target_domain, anchor)."""
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_db_session.execute.return_value = mock_result

        aggregator = AnchorsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        call_args = mock_db_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "GROUP BY" in sql_text or "group by" in sql_text.lower()

    @pytest.mark.asyncio
    async def test_build_for_snapshot_commits_transaction(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that build_for_snapshot commits the transaction."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_db_session.execute.return_value = mock_result

        aggregator = AnchorsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        mock_db_session.commit.assert_called_once()


class TestAnchorsAggregatorNormalization:
    """Tests for anchor text normalization."""

    @pytest.mark.asyncio
    async def test_anchor_text_is_trimmed(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that anchor text whitespace is trimmed."""
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_db_session.execute.return_value = mock_result

        aggregator = AnchorsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        # Verify SQL contains TRIM function
        call_args = mock_db_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "TRIM" in sql_text or "trim" in sql_text.lower()

    @pytest.mark.asyncio
    async def test_empty_anchors_are_skipped(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that empty anchor strings are excluded from aggregation."""
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_db_session.execute.return_value = mock_result

        aggregator = AnchorsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        # Verify SQL excludes empty strings
        call_args = mock_db_session.execute.call_args
        sql_text = str(call_args[0][0])
        # Should have a condition excluding empty anchors
        assert "!= ''" in sql_text or "<> ''" in sql_text or "anchor IS NOT NULL" in sql_text

    @pytest.mark.asyncio
    async def test_null_anchors_are_skipped(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that NULL anchor values are excluded from aggregation."""
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_db_session.execute.return_value = mock_result

        aggregator = AnchorsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        # Verify SQL excludes NULL anchors
        call_args = mock_db_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "IS NOT NULL" in sql_text or "is not null" in sql_text.lower()


class TestAnchorsAggregatorCounts:
    """Tests for anchor count calculations."""

    @pytest.mark.asyncio
    async def test_anchor_counts_aggregated_correctly(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that count is calculated as COUNT(*) per domain-anchor pair."""
        mock_result = MagicMock()
        mock_result.rowcount = 4
        mock_db_session.execute.return_value = mock_result

        aggregator = AnchorsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        # Verify SQL contains COUNT aggregation
        call_args = mock_db_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "COUNT" in sql_text or "count" in sql_text.lower()

    @pytest.mark.asyncio
    async def test_duplicate_anchors_after_trim_are_merged(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that anchors that become identical after TRIM are merged."""
        mock_result = MagicMock()
        mock_result.rowcount = 2  # "Example Link" and "  Example Link  " should merge
        mock_db_session.execute.return_value = mock_result

        aggregator = AnchorsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        # The GROUP BY should use TRIM(anchor) so duplicates merge
        call_args = mock_db_session.execute.call_args
        sql_text = str(call_args[0][0])
        # Should group by trimmed anchor
        assert "TRIM" in sql_text


class TestAnchorsAggregatorEmptyResults:
    """Tests for handling empty result sets."""

    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_snapshot(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that build_for_snapshot returns 0 when no valid anchors exist."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db_session.execute.return_value = mock_result

        aggregator = AnchorsAggregator(mock_db_session)
        count = await aggregator.build_for_snapshot(sample_snapshot_id)

        assert count == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_all_anchors_empty_or_null(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that returns 0 when all anchors are empty or NULL."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db_session.execute.return_value = mock_result

        aggregator = AnchorsAggregator(mock_db_session)
        count = await aggregator.build_for_snapshot(sample_snapshot_id)

        assert count == 0


class TestAnchorsAggregatorUpsert:
    """Tests for upsert behavior on conflict."""

    @pytest.mark.asyncio
    async def test_on_conflict_updates_count(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that ON CONFLICT updates the count value."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_db_session.execute.return_value = mock_result

        aggregator = AnchorsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        # SQL should contain ON CONFLICT with DO UPDATE
        call_args = mock_db_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "ON CONFLICT" in sql_text or "on conflict" in sql_text.lower()
        assert "UPDATE" in sql_text or "update" in sql_text.lower()


class TestAnchorsAggregatorErrorHandling:
    """Tests for error handling in AnchorsAggregator."""

    @pytest.mark.asyncio
    async def test_build_for_snapshot_handles_database_error(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that database errors are propagated properly."""
        mock_db_session.execute.side_effect = Exception("Database connection failed")

        aggregator = AnchorsAggregator(mock_db_session)

        with pytest.raises(Exception) as exc_info:
            await aggregator.build_for_snapshot(sample_snapshot_id)

        assert "Database connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rollback_on_error(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that transaction is rolled back on error."""
        mock_db_session.execute.side_effect = Exception("Query failed")

        aggregator = AnchorsAggregator(mock_db_session)

        with pytest.raises(Exception, match="Query failed"):
            await aggregator.build_for_snapshot(sample_snapshot_id)

        # Commit should not have been called due to error
        mock_db_session.commit.assert_not_called()
