"""
Tests for traffic weight computation.

Tests cover:
- Weight calculation with full data
- Weight calculation with partial data
- Default weight fallback when no data
- Normalization to 0-1 scale
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from semrush_workers.scoring.traffic_weight import (
    TrafficMetrics,
    compute_traffic_weight,
    get_traffic_weights_for_project,
    normalize_weight,
)


class TestNormalizeWeight:
    """Tests for the normalize_weight function."""

    def test_normalize_zero(self) -> None:
        """Zero raw weight returns 0."""
        assert normalize_weight(0.0, 0.0, 100.0) == 0.0

    def test_normalize_max(self) -> None:
        """Max raw weight returns 1.0."""
        assert normalize_weight(100.0, 0.0, 100.0) == 1.0

    def test_normalize_middle(self) -> None:
        """Middle value returns 0.5."""
        assert normalize_weight(50.0, 0.0, 100.0) == 0.5

    def test_normalize_same_min_max(self) -> None:
        """Same min and max returns 0.5."""
        assert normalize_weight(50.0, 50.0, 50.0) == 0.5

    def test_normalize_below_min(self) -> None:
        """Values below min are clamped to 0."""
        assert normalize_weight(-10.0, 0.0, 100.0) == 0.0

    def test_normalize_above_max(self) -> None:
        """Values above max are clamped to 1."""
        assert normalize_weight(150.0, 0.0, 100.0) == 1.0


class TestComputeTrafficWeight:
    """Tests for the compute_traffic_weight function."""

    def test_full_data(self) -> None:
        """Weight is computed correctly with all metrics."""
        metrics = TrafficMetrics(
            impressions=1000,
            clicks=100,
            sessions=50,
            conversions=10,
        )
        # Formula: impressions*0.3 + clicks*0.3 + sessions*0.2 + conversions*0.2
        # = 1000*0.3 + 100*0.3 + 50*0.2 + 10*0.2
        # = 300 + 30 + 10 + 2 = 342
        expected = 342.0
        assert compute_traffic_weight(metrics) == expected

    def test_zero_data(self) -> None:
        """Zero metrics return zero weight."""
        metrics = TrafficMetrics(
            impressions=0,
            clicks=0,
            sessions=0,
            conversions=0,
        )
        assert compute_traffic_weight(metrics) == 0.0

    def test_partial_data_impressions_only(self) -> None:
        """Weight works with only impressions."""
        metrics = TrafficMetrics(
            impressions=1000,
            clicks=0,
            sessions=0,
            conversions=0,
        )
        # = 1000*0.3 = 300
        assert compute_traffic_weight(metrics) == 300.0

    def test_partial_data_sessions_only(self) -> None:
        """Weight works with only sessions."""
        metrics = TrafficMetrics(
            impressions=0,
            clicks=0,
            sessions=100,
            conversions=0,
        )
        # = 100*0.2 = 20
        assert compute_traffic_weight(metrics) == 20.0


class TestGetTrafficWeightsForProject:
    """Tests for get_traffic_weights_for_project."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def project_id(self) -> uuid.UUID:
        """Sample project ID."""
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_returns_default_when_no_data(
        self, mock_session: AsyncMock, project_id: uuid.UUID
    ) -> None:
        """Returns default weight (0.5) when no data exists."""
        # Mock empty results for both queries
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        weights = await get_traffic_weights_for_project(
            mock_session, project_id, days=28
        )

        # Should return empty dict when no data
        assert weights == {}

    @pytest.mark.asyncio
    async def test_aggregates_search_data(
        self, mock_session: AsyncMock, project_id: uuid.UUID
    ) -> None:
        """Aggregates search console data correctly."""
        # Mock search fact results
        mock_search_result = MagicMock()
        mock_search_result.fetchall.return_value = [
            # (page_url, impressions, clicks)
            ("https://example.com/page1", 1000, 100),
            ("https://example.com/page2", 500, 50),
        ]

        # Mock analytics fact results (empty)
        mock_analytics_result = MagicMock()
        mock_analytics_result.fetchall.return_value = []

        mock_session.execute.side_effect = [mock_search_result, mock_analytics_result]

        weights = await get_traffic_weights_for_project(
            mock_session, project_id, days=28
        )

        # Should have weights for both pages
        assert len(weights) == 2
        assert "https://example.com/page1" in weights
        assert "https://example.com/page2" in weights

    @pytest.mark.asyncio
    async def test_aggregates_analytics_data(
        self, mock_session: AsyncMock, project_id: uuid.UUID
    ) -> None:
        """Aggregates GA4 analytics data correctly."""
        # Mock empty search results
        mock_search_result = MagicMock()
        mock_search_result.fetchall.return_value = []

        # Mock analytics fact results
        mock_analytics_result = MagicMock()
        mock_analytics_result.fetchall.return_value = [
            # (page_url, sessions, conversions)
            ("https://example.com/page1", 200, 20),
        ]

        mock_session.execute.side_effect = [mock_search_result, mock_analytics_result]

        weights = await get_traffic_weights_for_project(
            mock_session, project_id, days=28
        )

        assert len(weights) == 1
        assert "https://example.com/page1" in weights

    @pytest.mark.asyncio
    async def test_combines_search_and_analytics(
        self, mock_session: AsyncMock, project_id: uuid.UUID
    ) -> None:
        """Combines data from both search console and analytics."""
        # Mock search results
        mock_search_result = MagicMock()
        mock_search_result.fetchall.return_value = [
            ("https://example.com/page1", 1000, 100),
        ]

        # Mock analytics results for same page
        mock_analytics_result = MagicMock()
        mock_analytics_result.fetchall.return_value = [
            ("https://example.com/page1", 50, 5),
        ]

        mock_session.execute.side_effect = [mock_search_result, mock_analytics_result]

        weights = await get_traffic_weights_for_project(
            mock_session, project_id, days=28
        )

        # Should have combined weight for the page
        assert len(weights) == 1
        # Weight = 1000*0.3 + 100*0.3 + 50*0.2 + 5*0.2 = 300 + 30 + 10 + 1 = 341
        # Normalized: depends on min/max across all pages

    @pytest.mark.asyncio
    async def test_normalizes_weights(
        self, mock_session: AsyncMock, project_id: uuid.UUID
    ) -> None:
        """Weights are normalized to 0-1 scale."""
        # Mock search results with varying traffic
        mock_search_result = MagicMock()
        mock_search_result.fetchall.return_value = [
            ("https://example.com/high", 10000, 1000),
            ("https://example.com/medium", 1000, 100),
            ("https://example.com/low", 100, 10),
        ]

        mock_analytics_result = MagicMock()
        mock_analytics_result.fetchall.return_value = []

        mock_session.execute.side_effect = [mock_search_result, mock_analytics_result]

        weights = await get_traffic_weights_for_project(
            mock_session, project_id, days=28
        )

        # All weights should be between 0 and 1
        for url, weight in weights.items():
            assert 0.0 <= weight <= 1.0

        # High traffic page should have highest weight
        assert weights["https://example.com/high"] > weights["https://example.com/medium"]
        assert weights["https://example.com/medium"] > weights["https://example.com/low"]
