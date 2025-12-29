"""
Tests for RefDomainsAggregator.

Tests the aggregation of raw edges into referring domain aggregates,
including backlink counts and first_seen/last_seen tracking.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from semrush_commoncrawl.aggregates.refdomains import RefDomainsAggregator


class TestRefDomainsAggregatorBuildForSnapshot:
    """Tests for RefDomainsAggregator.build_for_snapshot method."""

    @pytest.mark.asyncio
    async def test_build_for_snapshot_creates_aggregates(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that build_for_snapshot creates correct refdomains aggregates."""
        # Configure mock to return rowcount from execute
        mock_result = MagicMock()
        mock_result.rowcount = 4  # 4 unique ref domains
        mock_db_session.execute.return_value = mock_result

        aggregator = RefDomainsAggregator(mock_db_session)
        count = await aggregator.build_for_snapshot(sample_snapshot_id)

        # Should have executed the aggregation query
        assert mock_db_session.execute.called
        assert count == 4

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

        aggregator = RefDomainsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        # Check that execute was called with the snapshot_id parameter
        call_args = mock_db_session.execute.call_args
        assert call_args is not None

        # The SQL should contain key aggregation elements
        sql_text = str(call_args[0][0])
        assert "commoncrawl_refdomains" in sql_text.lower() or "INSERT" in sql_text
        assert "commoncrawl_edges" in sql_text.lower() or "SELECT" in sql_text

    @pytest.mark.asyncio
    async def test_build_for_snapshot_groups_by_domain_pairs(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that aggregation groups by (target_domain, source_domain)."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_db_session.execute.return_value = mock_result

        aggregator = RefDomainsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        # Verify the SQL contains GROUP BY clause
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
        mock_result.rowcount = 5
        mock_db_session.execute.return_value = mock_result

        aggregator = RefDomainsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_for_snapshot_returns_zero_for_empty_snapshot(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that build_for_snapshot returns 0 when no edges exist."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db_session.execute.return_value = mock_result

        aggregator = RefDomainsAggregator(mock_db_session)
        count = await aggregator.build_for_snapshot(sample_snapshot_id)

        assert count == 0


class TestRefDomainsAggregatorRebuildForDomain:
    """Tests for RefDomainsAggregator.rebuild_for_domain method."""

    @pytest.mark.asyncio
    async def test_rebuild_for_domain_filters_by_target(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
        sample_target_domain: str,
    ) -> None:
        """Test that rebuild_for_domain filters edges by target domain."""
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_db_session.execute.return_value = mock_result

        aggregator = RefDomainsAggregator(mock_db_session)
        count = await aggregator.rebuild_for_domain(sample_target_domain, sample_snapshot_id)

        # Should return the count of rebuilt records
        assert count == 2
        assert mock_db_session.execute.called

    @pytest.mark.asyncio
    async def test_rebuild_for_domain_uses_domain_filter(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
        sample_target_domain: str,
    ) -> None:
        """Test that rebuild uses WHERE clause with target_domain."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        aggregator = RefDomainsAggregator(mock_db_session)
        await aggregator.rebuild_for_domain(sample_target_domain, sample_snapshot_id)

        # The SQL should reference target_domain parameter
        call_args = mock_db_session.execute.call_args
        assert call_args is not None
        sql_text = str(call_args[0][0])
        assert "target_domain" in sql_text.lower()

    @pytest.mark.asyncio
    async def test_rebuild_for_domain_updates_existing_records(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
        sample_target_domain: str,
    ) -> None:
        """Test that rebuild updates existing records via ON CONFLICT."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_db_session.execute.return_value = mock_result

        aggregator = RefDomainsAggregator(mock_db_session)
        await aggregator.rebuild_for_domain(sample_target_domain, sample_snapshot_id)

        # SQL should contain ON CONFLICT for upsert behavior
        call_args = mock_db_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "ON CONFLICT" in sql_text or "on conflict" in sql_text.lower()


class TestRefDomainsAggregatorCounts:
    """Tests for verifying correct backlink count calculations."""

    @pytest.mark.asyncio
    async def test_backlink_counts_aggregated_correctly(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that backlink_count is calculated as COUNT(*) per domain pair."""
        mock_result = MagicMock()
        mock_result.rowcount = 4
        mock_db_session.execute.return_value = mock_result

        aggregator = RefDomainsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        # Verify SQL contains COUNT aggregation
        call_args = mock_db_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "COUNT" in sql_text or "count" in sql_text.lower()


class TestRefDomainsAggregatorTimestamps:
    """Tests for first_seen/last_seen timestamp tracking."""

    @pytest.mark.asyncio
    async def test_first_seen_uses_min_discovered_at(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that first_seen is calculated as MIN(discovered_at)."""
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_db_session.execute.return_value = mock_result

        aggregator = RefDomainsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        # Verify SQL contains MIN aggregation for first_seen
        call_args = mock_db_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "MIN" in sql_text or "min" in sql_text.lower()

    @pytest.mark.asyncio
    async def test_last_seen_uses_max_discovered_at(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that last_seen is calculated as MAX(discovered_at)."""
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_db_session.execute.return_value = mock_result

        aggregator = RefDomainsAggregator(mock_db_session)
        await aggregator.build_for_snapshot(sample_snapshot_id)

        # Verify SQL contains MAX aggregation for last_seen
        call_args = mock_db_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "MAX" in sql_text or "max" in sql_text.lower()


class TestRefDomainsAggregatorErrorHandling:
    """Tests for error handling in RefDomainsAggregator."""

    @pytest.mark.asyncio
    async def test_build_for_snapshot_handles_database_error(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
    ) -> None:
        """Test that database errors are propagated properly."""
        mock_db_session.execute.side_effect = Exception("Database connection failed")

        aggregator = RefDomainsAggregator(mock_db_session)

        with pytest.raises(Exception) as exc_info:
            await aggregator.build_for_snapshot(sample_snapshot_id)

        assert "Database connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rebuild_for_domain_handles_database_error(
        self,
        mock_db_session: AsyncMock,
        sample_snapshot_id: str,
        sample_target_domain: str,
    ) -> None:
        """Test that database errors during rebuild are propagated."""
        mock_db_session.execute.side_effect = Exception("Query timeout")

        aggregator = RefDomainsAggregator(mock_db_session)

        with pytest.raises(Exception) as exc_info:
            await aggregator.rebuild_for_domain(sample_target_domain, sample_snapshot_id)

        assert "Query timeout" in str(exc_info.value)
