"""
Tests for report context builders.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from semrush_reports.builders import (
    build_audit_context,
    build_backlinks_context,
    build_overview_context,
    build_performance_context,
)


class TestBuildAuditContext:
    """Tests for build_audit_context function."""

    @pytest.mark.asyncio
    async def test_build_audit_context_project_not_found(
        self,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test build_audit_context with non-existent project."""
        # Setup mock to return None for project
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        project_id = uuid.uuid4()

        with pytest.raises(ValueError, match=r"Project .* not found"):
            await build_audit_context(mock_db_session, project_id)

    @pytest.mark.asyncio
    async def test_build_audit_context_empty_crawl(
        self,
        mock_db_session: AsyncMock,
        mock_project: MagicMock,
    ) -> None:
        """Test build_audit_context with no crawl runs."""
        # Setup mock to return project but no crawl
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = mock_project

        mock_crawl_result = MagicMock()
        mock_crawl_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_project_result, mock_crawl_result]

        context = await build_audit_context(mock_db_session, mock_project.id)

        # Verify empty context
        assert context["project_name"] == "Test Project"
        assert context["issues_summary"]["total"] == 0
        assert context["crawl_stats"]["pages_crawled"] == 0

    @pytest.mark.asyncio
    async def test_build_audit_context_with_data(
        self,
        mock_db_session: AsyncMock,
        mock_project: MagicMock,
        mock_crawl_run: MagicMock,
        mock_issues: list[MagicMock],
        mock_crawl_pages: list[MagicMock],
    ) -> None:
        """Test build_audit_context with full data."""
        # Setup mock results in order
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = mock_project

        mock_crawl_result = MagicMock()
        mock_crawl_result.scalar_one_or_none.return_value = mock_crawl_run

        # Issues query returns tuples of (issue, issue_type)
        mock_issues_result = MagicMock()
        mock_issues_result.all.return_value = [(issue, issue.issue_type) for issue in mock_issues]

        mock_pages_result = MagicMock()
        mock_pages_result.scalars.return_value.all.return_value = mock_crawl_pages

        mock_db_session.execute.side_effect = [
            mock_project_result,
            mock_crawl_result,
            mock_issues_result,
            mock_pages_result,
        ]

        context = await build_audit_context(mock_db_session, mock_project.id)

        # Verify context has data
        assert context["project_name"] == "Test Project"
        assert context["issues_summary"]["total"] == 5
        assert context["crawl_stats"]["pages_crawled"] == 5
        assert "issues_by_category" in context
        assert "top_issues" in context
        assert "recommendations" in context

    @pytest.mark.asyncio
    async def test_build_audit_context_with_params(
        self,
        mock_db_session: AsyncMock,
        mock_project: MagicMock,
        mock_crawl_run: MagicMock,
        mock_issues: list[MagicMock],
        mock_crawl_pages: list[MagicMock],
    ) -> None:
        """Test build_audit_context with custom parameters."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = mock_project

        mock_crawl_result = MagicMock()
        mock_crawl_result.scalar_one_or_none.return_value = mock_crawl_run

        mock_issues_result = MagicMock()
        mock_issues_result.all.return_value = [(issue, issue.issue_type) for issue in mock_issues]

        mock_pages_result = MagicMock()
        mock_pages_result.scalars.return_value.all.return_value = mock_crawl_pages

        mock_db_session.execute.side_effect = [
            mock_project_result,
            mock_crawl_result,
            mock_issues_result,
            mock_pages_result,
        ]

        params = {
            "crawl_run_id": mock_crawl_run.id,
            "date_start": datetime(2024, 1, 1, tzinfo=UTC),
            "date_end": datetime(2024, 1, 31, tzinfo=UTC),
        }

        context = await build_audit_context(mock_db_session, mock_project.id, params)

        assert context["date_range"]["start"] == "2024-01-01"
        assert context["date_range"]["end"] == "2024-01-31"


class TestBuildPerformanceContext:
    """Tests for build_performance_context function."""

    @pytest.mark.asyncio
    async def test_build_performance_context_project_not_found(
        self,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test build_performance_context with non-existent project."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        project_id = uuid.uuid4()

        with pytest.raises(ValueError, match=r"Project .* not found"):
            await build_performance_context(mock_db_session, project_id)

    @pytest.mark.asyncio
    async def test_build_performance_context_empty_data(
        self,
        mock_db_session: AsyncMock,
        mock_project: MagicMock,
    ) -> None:
        """Test build_performance_context with no search facts."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = mock_project

        mock_facts_result = MagicMock()
        mock_facts_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_project_result, mock_facts_result]

        context = await build_performance_context(mock_db_session, mock_project.id)

        assert context["project_name"] == "Test Project"
        assert context["summary"]["total_clicks"] == 0
        assert context["summary"]["total_impressions"] == 0
        assert context["top_queries"] == []

    @pytest.mark.asyncio
    async def test_build_performance_context_with_data(
        self,
        mock_db_session: AsyncMock,
        mock_project: MagicMock,
        mock_search_facts: list[MagicMock],
    ) -> None:
        """Test build_performance_context with search facts."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = mock_project

        mock_facts_result = MagicMock()
        mock_facts_result.scalars.return_value.all.return_value = mock_search_facts

        mock_prev_facts_result = MagicMock()
        mock_prev_facts_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [
            mock_project_result,
            mock_facts_result,
            mock_prev_facts_result,
        ]

        context = await build_performance_context(mock_db_session, mock_project.id)

        assert context["project_name"] == "Test Project"
        assert context["summary"]["total_clicks"] > 0
        assert context["summary"]["total_impressions"] > 0
        assert "top_queries" in context
        assert "top_pages" in context
        assert "top_countries" in context
        assert "devices" in context

    @pytest.mark.asyncio
    async def test_build_performance_context_with_trends(
        self,
        mock_db_session: AsyncMock,
        mock_project: MagicMock,
        mock_search_facts: list[MagicMock],
    ) -> None:
        """Test build_performance_context calculates trends correctly."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = mock_project

        mock_facts_result = MagicMock()
        mock_facts_result.scalars.return_value.all.return_value = mock_search_facts

        # Create previous period facts with lower values
        prev_facts = []
        for f in mock_search_facts:
            prev_fact = MagicMock()
            prev_fact.clicks = f.clicks // 2
            prev_fact.impressions = f.impressions // 2
            prev_fact.avg_position = f.avg_position
            prev_fact.query = f.query
            prev_fact.page_url = f.page_url
            prev_fact.country = f.country
            prev_fact.device = f.device
            prev_facts.append(prev_fact)

        mock_prev_facts_result = MagicMock()
        mock_prev_facts_result.scalars.return_value.all.return_value = prev_facts

        mock_db_session.execute.side_effect = [
            mock_project_result,
            mock_facts_result,
            mock_prev_facts_result,
        ]

        context = await build_performance_context(mock_db_session, mock_project.id)

        # Should show positive growth since current > previous
        assert "trends" in context
        assert context["trends"]["clicks_change"] > 0


class TestBuildBacklinksContext:
    """Tests for build_backlinks_context function."""

    @pytest.mark.asyncio
    async def test_build_backlinks_context_project_not_found(
        self,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test build_backlinks_context with non-existent project."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        project_id = uuid.uuid4()

        with pytest.raises(ValueError, match=r"Project .* not found"):
            await build_backlinks_context(mock_db_session, project_id)

    @pytest.mark.asyncio
    async def test_build_backlinks_context_empty_data(
        self,
        mock_db_session: AsyncMock,
        mock_project: MagicMock,
    ) -> None:
        """Test build_backlinks_context with no backlinks."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = mock_project

        mock_backlinks_result = MagicMock()
        mock_backlinks_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_project_result, mock_backlinks_result]

        context = await build_backlinks_context(mock_db_session, mock_project.id)

        assert context["project_name"] == "Test Project"
        assert context["summary"]["total_backlinks"] == 0
        assert context["top_referring_domains"] == []

    @pytest.mark.asyncio
    async def test_build_backlinks_context_with_data(
        self,
        mock_db_session: AsyncMock,
        mock_project: MagicMock,
        mock_backlinks: list[MagicMock],
    ) -> None:
        """Test build_backlinks_context with backlinks data."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = mock_project

        mock_backlinks_result = MagicMock()
        mock_backlinks_result.scalars.return_value.all.return_value = mock_backlinks

        mock_db_session.execute.side_effect = [mock_project_result, mock_backlinks_result]

        context = await build_backlinks_context(mock_db_session, mock_project.id)

        assert context["project_name"] == "Test Project"
        assert context["summary"]["total_backlinks"] == 5
        assert "distribution" in context
        assert "top_referring_domains" in context
        assert "top_anchor_texts" in context
        assert "top_target_urls" in context
        assert "new_backlinks" in context


class TestBuildOverviewContext:
    """Tests for build_overview_context function."""

    @pytest.mark.asyncio
    async def test_build_overview_context_project_not_found(
        self,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test build_overview_context with non-existent project."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        project_id = uuid.uuid4()

        with pytest.raises(ValueError, match=r"Project .* not found"):
            await build_overview_context(mock_db_session, project_id)

    @pytest.mark.asyncio
    async def test_build_overview_context_combines_data(
        self,
        mock_db_session: AsyncMock,
        mock_project: MagicMock,
        mock_crawl_run: MagicMock,
        mock_issues: list[MagicMock],
        mock_crawl_pages: list[MagicMock],
        mock_backlinks: list[MagicMock],
        mock_search_facts: list[MagicMock],
    ) -> None:
        """Test build_overview_context combines all report data."""
        # Setup comprehensive mock chain for all three sub-contexts
        # Overview calls build_audit_context, build_backlinks_context, build_performance_context

        # For the overview project lookup
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = mock_project

        # For audit context
        mock_audit_project_result = MagicMock()
        mock_audit_project_result.scalar_one_or_none.return_value = mock_project

        mock_crawl_result = MagicMock()
        mock_crawl_result.scalar_one_or_none.return_value = mock_crawl_run

        mock_issues_result = MagicMock()
        mock_issues_result.all.return_value = [(issue, issue.issue_type) for issue in mock_issues]

        mock_pages_result = MagicMock()
        mock_pages_result.scalars.return_value.all.return_value = mock_crawl_pages

        # For backlinks context
        mock_backlinks_project_result = MagicMock()
        mock_backlinks_project_result.scalar_one_or_none.return_value = mock_project

        mock_backlinks_result = MagicMock()
        mock_backlinks_result.scalars.return_value.all.return_value = mock_backlinks

        # For performance context
        mock_perf_project_result = MagicMock()
        mock_perf_project_result.scalar_one_or_none.return_value = mock_project

        mock_facts_result = MagicMock()
        mock_facts_result.scalars.return_value.all.return_value = mock_search_facts

        mock_prev_facts_result = MagicMock()
        mock_prev_facts_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [
            mock_project_result,  # Overview project lookup
            mock_audit_project_result,  # Audit project lookup
            mock_crawl_result,  # Audit crawl lookup
            mock_issues_result,  # Audit issues
            mock_pages_result,  # Audit pages
            mock_backlinks_project_result,  # Backlinks project lookup
            mock_backlinks_result,  # Backlinks data
            mock_perf_project_result,  # Performance project lookup
            mock_facts_result,  # Performance facts
            mock_prev_facts_result,  # Performance previous period
        ]

        context = await build_overview_context(mock_db_session, mock_project.id)

        # Verify combined context
        assert context["project_name"] == "Test Project"
        assert "health_score" in context
        assert "audit" in context
        assert "backlinks" in context
        assert "performance" in context
        assert "recommendations" in context
        assert "action_items" in context

        # Verify audit section
        assert "critical" in context["audit"]
        assert "high" in context["audit"]
        assert "issues_total" in context["audit"]

        # Verify backlinks section
        assert "total_backlinks" in context["backlinks"]
        assert "referring_domains" in context["backlinks"]

        # Verify performance section
        assert "total_clicks" in context["performance"]
        assert "avg_ctr" in context["performance"]


# Additional fixtures for performance tests


@pytest.fixture
def mock_search_facts() -> list[MagicMock]:
    """Create mock search facts."""
    facts = []
    for i in range(10):
        fact = MagicMock()
        fact.clicks = 100 + i * 10
        fact.impressions = 1000 + i * 100
        fact.ctr = Decimal("0.1")
        fact.avg_position = Decimal(str(5 + i * 0.5))
        fact.query = f"test query {i}" if i < 5 else None
        fact.page_url = f"https://example.com/page-{i}" if i >= 3 else None
        fact.country = ["US", "UK", "DE", "FR", "CA"][i % 5]
        fact.device = ["desktop", "mobile", "tablet"][i % 3]
        fact.engine = "google"
        fact.date = date(2024, 1, 15)
        facts.append(fact)
    return facts
