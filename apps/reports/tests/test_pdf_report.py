"""
Tests for PDF report service.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from semrush_reports.pdf_report import PDFRenderer, ReportBuilder


class TestPDFRenderer:
    """Tests for PDFRenderer class."""

    def test_init_default_template_dir(self) -> None:
        """Test PDFRenderer uses default template directory."""
        renderer = PDFRenderer()
        assert renderer.template_dir.exists()
        assert renderer.template_dir.name == "templates"

    def test_init_custom_template_dir(self, tmp_path: Path) -> None:
        """Test PDFRenderer with custom template directory."""
        renderer = PDFRenderer(template_dir=tmp_path)
        assert renderer.template_dir == tmp_path

    def test_render_html(self, tmp_path: Path) -> None:
        """Test HTML rendering from template."""
        # Create a simple template
        template_file = tmp_path / "test.html"
        template_file.write_text("<html><body>{{ name }}</body></html>")

        renderer = PDFRenderer(template_dir=tmp_path)
        result = renderer.render_html("test.html", {"name": "Test"})

        assert "<html>" in result
        assert "Test" in result

    def test_render_html_with_base_template(self) -> None:
        """Test HTML rendering with base template."""
        renderer = PDFRenderer()

        # Use existing audit_report template
        context = {
            "project_name": "Test Project",
            "generated_at": "2024-01-15 10:00 UTC",
            "date_range": {"start": "2024-01-01", "end": "2024-01-15"},
            "issues_summary": {"critical": 5, "high": 10, "medium": 20, "low": 30, "total": 65},
            "issues_by_category": {},
            "top_issues": [],
            "affected_urls": [],
            "crawl_stats": {
                "pages_crawled": 100,
                "pages_with_issues": 50,
                "avg_response_time": 200,
                "error_rate": 5.0,
            },
            "status_codes": [],
            "recommendations": [],
        }

        result = renderer.render_html("audit_report.html", context)

        assert "Test Project" in result
        assert "Site Audit Report" in result
        assert "Critical" in result


class TestReportBuilder:
    """Tests for ReportBuilder class."""

    @pytest.mark.asyncio
    async def test_build_audit_context_project_not_found(
        self,
        mock_db_session: AsyncMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test build_audit_context with non-existent project."""
        # Setup mock to return None for project
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        builder = ReportBuilder(mock_db_session)

        with pytest.raises(ValueError, match="Project .* not found"):
            await builder.build_audit_context(test_project_id)

    @pytest.mark.asyncio
    async def test_build_audit_context_empty_crawl(
        self,
        mock_db_session: AsyncMock,
        mock_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test build_audit_context with no crawl runs."""
        # Setup mock to return project but no crawl
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = mock_project

        mock_crawl_result = MagicMock()
        mock_crawl_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_project_result, mock_crawl_result]

        builder = ReportBuilder(mock_db_session)
        context = await builder.build_audit_context(test_project_id)

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
        test_project_id: uuid.UUID,
    ) -> None:
        """Test build_audit_context with full data."""
        # Setup mock results in order
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = mock_project

        mock_crawl_result = MagicMock()
        mock_crawl_result.scalar_one_or_none.return_value = mock_crawl_run

        # Issues query returns tuples of (issue, issue_type)
        mock_issues_result = MagicMock()
        mock_issues_result.all.return_value = [
            (issue, issue.issue_type) for issue in mock_issues
        ]

        mock_pages_result = MagicMock()
        mock_pages_result.scalars.return_value.all.return_value = mock_crawl_pages

        mock_db_session.execute.side_effect = [
            mock_project_result,
            mock_crawl_result,
            mock_issues_result,
            mock_pages_result,
        ]

        builder = ReportBuilder(mock_db_session)
        context = await builder.build_audit_context(test_project_id)

        # Verify context has data
        assert context["project_name"] == "Test Project"
        assert context["issues_summary"]["total"] == 5
        assert context["crawl_stats"]["pages_crawled"] == 5
        assert "issues_by_category" in context
        assert "top_issues" in context

    @pytest.mark.asyncio
    async def test_build_backlinks_context_project_not_found(
        self,
        mock_db_session: AsyncMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test build_backlinks_context with non-existent project."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        builder = ReportBuilder(mock_db_session)

        with pytest.raises(ValueError, match="Project .* not found"):
            await builder.build_backlinks_context(test_project_id)

    @pytest.mark.asyncio
    async def test_build_backlinks_context_with_data(
        self,
        mock_db_session: AsyncMock,
        mock_project: MagicMock,
        mock_backlinks: list[MagicMock],
        test_project_id: uuid.UUID,
    ) -> None:
        """Test build_backlinks_context with full data."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = mock_project

        mock_backlinks_result = MagicMock()
        mock_backlinks_result.scalars.return_value.all.return_value = mock_backlinks

        mock_db_session.execute.side_effect = [mock_project_result, mock_backlinks_result]

        builder = ReportBuilder(mock_db_session)
        context = await builder.build_backlinks_context(test_project_id)

        # Verify context
        assert context["project_name"] == "Test Project"
        assert context["summary"]["total_backlinks"] == 5
        assert "distribution" in context
        assert "top_referring_domains" in context
        assert "top_anchor_texts" in context

    def test_severity_label(self, mock_db_session: AsyncMock) -> None:
        """Test severity label conversion."""
        builder = ReportBuilder(mock_db_session)

        assert builder._severity_label(5) == "Critical"
        assert builder._severity_label(4) == "High"
        assert builder._severity_label(3) == "Medium"
        assert builder._severity_label(2) == "Low"
        assert builder._severity_label(1) == "Info"
        assert builder._severity_label(0) == "Unknown"

    def test_status_description(self, mock_db_session: AsyncMock) -> None:
        """Test HTTP status code description."""
        builder = ReportBuilder(mock_db_session)

        assert builder._status_description(200) == "OK"
        assert builder._status_description(301) == "Moved Permanently"
        assert builder._status_description(404) == "Not Found"
        assert builder._status_description(500) == "Internal Server Error"
        assert builder._status_description(999) == "HTTP 999"

    def test_generate_recommendations_critical_issues(
        self,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test recommendations generation with critical issues."""
        builder = ReportBuilder(mock_db_session)

        severity_counts = {"critical": 5, "high": 10, "medium": 20, "low": 30, "total": 65}
        top_issues: list[dict] = []

        recs = builder._generate_recommendations(severity_counts, top_issues)

        assert len(recs) > 0
        assert any("Critical" in rec["title"] for rec in recs)

    def test_generate_recommendations_broken_links(
        self,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test recommendations for broken links."""
        builder = ReportBuilder(mock_db_session)

        severity_counts = {"critical": 0, "high": 0, "medium": 5, "low": 10, "total": 15}
        top_issues = [
            {"type": "broken_link_404", "count": 10, "category": "links", "severity": 3}
        ]

        recs = builder._generate_recommendations(severity_counts, top_issues)

        assert any("Broken Links" in rec["title"] for rec in recs)
