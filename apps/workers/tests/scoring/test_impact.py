"""
Tests for impact score computation.

Tests cover:
- Impact score formula: severity * confidence * traffic_weight
- Handling pages without traffic data
- Batch update of issue instances
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from semrush_workers.rules.models import IssueInstance, IssueSeverity
from semrush_workers.scoring.impact import (
    compute_impact_score,
    compute_impact_scores,
    normalize_url,
)


class TestNormalizeUrl:
    """Tests for URL normalization."""

    def test_removes_trailing_slash(self) -> None:
        """Trailing slashes are removed."""
        assert normalize_url("https://example.com/") == "https://example.com"

    def test_keeps_path(self) -> None:
        """Paths are preserved."""
        assert normalize_url("https://example.com/page") == "https://example.com/page"

    def test_lowercases_scheme_and_host(self) -> None:
        """Scheme and host are lowercased."""
        assert normalize_url("HTTPS://EXAMPLE.COM/Page") == "https://example.com/Page"

    def test_handles_query_params(self) -> None:
        """Query parameters are preserved."""
        url = "https://example.com/page?foo=bar"
        assert normalize_url(url) == url


class TestComputeImpactScore:
    """Tests for single impact score computation."""

    def test_basic_formula(self) -> None:
        """Score = severity * confidence * traffic_weight."""
        # severity=4, confidence=0.9, weight=0.8
        # 4 * 0.9 * 0.8 = 2.88
        score = compute_impact_score(
            severity=IssueSeverity.HIGH,
            confidence=0.9,
            traffic_weight=0.8,
        )
        assert score == pytest.approx(2.88, rel=0.01)

    def test_critical_severity(self) -> None:
        """Critical severity (5) with full confidence and weight."""
        score = compute_impact_score(
            severity=IssueSeverity.CRITICAL,
            confidence=1.0,
            traffic_weight=1.0,
        )
        assert score == 5.0

    def test_low_severity(self) -> None:
        """Low severity (2) with partial values."""
        score = compute_impact_score(
            severity=IssueSeverity.LOW,
            confidence=0.5,
            traffic_weight=0.5,
        )
        # 2 * 0.5 * 0.5 = 0.5
        assert score == 0.5

    def test_default_weight_when_no_data(self) -> None:
        """Uses default weight (0.5) when traffic_weight is None."""
        score = compute_impact_score(
            severity=IssueSeverity.MEDIUM,
            confidence=1.0,
            traffic_weight=None,
        )
        # 3 * 1.0 * 0.5 = 1.5
        assert score == 1.5


class TestComputeImpactScores:
    """Tests for batch impact score computation."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def crawl_run_id(self) -> uuid.UUID:
        """Sample crawl run ID."""
        return uuid.uuid4()

    @pytest.fixture
    def project_id(self) -> uuid.UUID:
        """Sample project ID."""
        return uuid.uuid4()

    @pytest.fixture
    def sample_issues(self, crawl_run_id: uuid.UUID) -> list[IssueInstance]:
        """Create sample issue instances."""
        return [
            IssueInstance(
                id=uuid.uuid4(),
                crawl_run_id=crawl_run_id,
                crawl_page_id=uuid.uuid4(),
                issue_type_id="missing_title",
                affected_url="https://example.com/page1",
                severity=IssueSeverity.HIGH,
                confidence=1.0,
                impact_score=None,
            ),
            IssueInstance(
                id=uuid.uuid4(),
                crawl_run_id=crawl_run_id,
                crawl_page_id=uuid.uuid4(),
                issue_type_id="thin_content",
                affected_url="https://example.com/page2",
                severity=IssueSeverity.LOW,
                confidence=0.75,
                impact_score=None,
            ),
        ]

    @pytest.mark.asyncio
    async def test_updates_all_issues(
        self,
        mock_session: AsyncMock,
        crawl_run_id: uuid.UUID,
        project_id: uuid.UUID,
        sample_issues: list[IssueInstance],
    ) -> None:
        """All issues get their impact scores computed."""
        # Mock traffic weights
        traffic_weights = {
            "https://example.com/page1": 0.8,
            "https://example.com/page2": 0.4,
        }

        with patch(
            "semrush_workers.scoring.impact.get_traffic_weights_for_project",
            return_value=traffic_weights,
        ):
            updated = await compute_impact_scores(
                session=mock_session,
                crawl_run_id=crawl_run_id,
                project_id=project_id,
                issues=sample_issues,
            )

        assert len(updated) == 2

        # page1: HIGH(4) * 1.0 * 0.8 = 3.2
        assert updated[0].impact_score == pytest.approx(3.2, rel=0.01)

        # page2: LOW(2) * 0.75 * 0.4 = 0.6
        assert updated[1].impact_score == pytest.approx(0.6, rel=0.01)

    @pytest.mark.asyncio
    async def test_uses_default_weight_for_unknown_pages(
        self,
        mock_session: AsyncMock,
        crawl_run_id: uuid.UUID,
        project_id: uuid.UUID,
        sample_issues: list[IssueInstance],
    ) -> None:
        """Pages not in traffic data get default weight (0.5)."""
        # Only page1 has traffic data
        traffic_weights = {
            "https://example.com/page1": 0.8,
        }

        with patch(
            "semrush_workers.scoring.impact.get_traffic_weights_for_project",
            return_value=traffic_weights,
        ):
            updated = await compute_impact_scores(
                session=mock_session,
                crawl_run_id=crawl_run_id,
                project_id=project_id,
                issues=sample_issues,
            )

        # page1: HIGH(4) * 1.0 * 0.8 = 3.2
        assert updated[0].impact_score == pytest.approx(3.2, rel=0.01)

        # page2 uses default weight: LOW(2) * 0.75 * 0.5 = 0.75
        assert updated[1].impact_score == pytest.approx(0.75, rel=0.01)

    @pytest.mark.asyncio
    async def test_empty_issues_list(
        self,
        mock_session: AsyncMock,
        crawl_run_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> None:
        """Empty issues list returns empty list."""
        with patch(
            "semrush_workers.scoring.impact.get_traffic_weights_for_project",
            return_value={},
        ):
            updated = await compute_impact_scores(
                session=mock_session,
                crawl_run_id=crawl_run_id,
                project_id=project_id,
                issues=[],
            )

        assert updated == []

    @pytest.mark.asyncio
    async def test_no_traffic_data_uses_default(
        self,
        mock_session: AsyncMock,
        crawl_run_id: uuid.UUID,
        project_id: uuid.UUID,
        sample_issues: list[IssueInstance],
    ) -> None:
        """When no traffic data exists, all pages use default weight."""
        with patch(
            "semrush_workers.scoring.impact.get_traffic_weights_for_project",
            return_value={},
        ):
            updated = await compute_impact_scores(
                session=mock_session,
                crawl_run_id=crawl_run_id,
                project_id=project_id,
                issues=sample_issues,
            )

        # All use default weight 0.5
        # page1: HIGH(4) * 1.0 * 0.5 = 2.0
        assert updated[0].impact_score == pytest.approx(2.0, rel=0.01)

        # page2: LOW(2) * 0.75 * 0.5 = 0.75
        assert updated[1].impact_score == pytest.approx(0.75, rel=0.01)
