"""
CSV export service for generating CSV exports.

Provides streaming CSV generation for:
- Issues export
- Backlinks export
- Crawl pages export
- Performance data export
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator, Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from semrush_core.models import CrawlPage, IssueInstance, ProjectBacklink
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class CSVExporter:
    """
    CSV export generator with streaming support.

    Generates CSV files with UTF-8 BOM for Excel compatibility
    and supports streaming for large datasets.
    """

    # UTF-8 BOM for Excel compatibility
    UTF8_BOM = "\ufeff"

    def __init__(self, include_bom: bool = True) -> None:
        """
        Initialize CSV exporter.

        Args:
            include_bom: Whether to include UTF-8 BOM for Excel compatibility.
        """
        self.include_bom = include_bom

    def _write_header(self, buffer: io.StringIO, headers: list[str]) -> None:
        """Write CSV header row with optional BOM."""
        if self.include_bom:
            buffer.write(self.UTF8_BOM)
        writer = csv.writer(buffer)
        writer.writerow(headers)

    def _write_rows(
        self,
        buffer: io.StringIO,
        rows: Iterable[list[Any]],
    ) -> None:
        """Write CSV data rows."""
        writer = csv.writer(buffer)
        for row in rows:
            writer.writerow(row)

    async def export_issues(
        self,
        db: AsyncSession,
        project_id: UUID,
        crawl_run_id: UUID | None = None,
        severity_min: int | None = None,
    ) -> bytes:
        """
        Export issues to CSV format.

        Args:
            db: Database session.
            project_id: Project UUID.
            crawl_run_id: Optional crawl run filter.
            severity_min: Minimum severity level filter.

        Returns:
            CSV file contents as bytes.
        """
        from semrush_core.models import CrawlRun, IssueType

        # Build query
        query = (
            select(IssueInstance)
            .join(CrawlRun)
            .join(IssueType)
            .where(CrawlRun.project_id == project_id)
        )

        if crawl_run_id is not None:
            query = query.where(IssueInstance.crawl_run_id == crawl_run_id)

        if severity_min is not None:
            query = query.where(IssueType.severity >= severity_min)

        query = query.order_by(IssueInstance.affected_url)

        result = await db.execute(query)
        issues = result.scalars().all()

        # Generate CSV
        buffer = io.StringIO()
        headers = [
            "URL",
            "Issue Type",
            "Category",
            "Severity",
            "Impact Score",
            "Confidence",
            "Evidence",
        ]
        self._write_header(buffer, headers)

        rows = []
        for issue in issues:
            # Get issue type info
            issue_type = issue.issue_type
            rows.append([
                issue.affected_url,
                issue_type.id if issue_type else "",
                issue_type.category if issue_type else "",
                issue_type.severity if issue_type else "",
                str(issue.impact_score) if issue.impact_score else "",
                str(issue.confidence) if issue.confidence else "",
                str(issue.evidence) if issue.evidence else "",
            ])

        self._write_rows(buffer, rows)
        return buffer.getvalue().encode("utf-8")

    async def export_backlinks(
        self,
        db: AsyncSession,
        project_id: UUID,
        source_type: str | None = None,
        source_domain: str | None = None,
    ) -> bytes:
        """
        Export backlinks to CSV format.

        Args:
            db: Database session.
            project_id: Project UUID.
            source_type: Optional filter by source type.
            source_domain: Optional filter by source domain.

        Returns:
            CSV file contents as bytes.
        """
        # Build query
        query = select(ProjectBacklink).where(ProjectBacklink.project_id == project_id)

        if source_type is not None:
            query = query.where(ProjectBacklink.source_type == source_type)

        if source_domain is not None:
            query = query.where(ProjectBacklink.source_domain.ilike(f"%{source_domain}%"))

        query = query.order_by(ProjectBacklink.source_domain, ProjectBacklink.source_url)

        result = await db.execute(query)
        backlinks = result.scalars().all()

        # Generate CSV
        buffer = io.StringIO()
        headers = [
            "Source URL",
            "Source Domain",
            "Target URL",
            "Target Domain",
            "Anchor Text",
            "Rel Flags",
            "Source Type",
            "Discovered At",
        ]
        self._write_header(buffer, headers)

        rows = []
        for bl in backlinks:
            rows.append([
                bl.source_url,
                bl.source_domain,
                bl.target_url,
                bl.target_domain,
                bl.anchor or "",
                ",".join(bl.rel_flags) if bl.rel_flags else "",
                bl.source_type,
                bl.discovered_at.isoformat() if bl.discovered_at else "",
            ])

        self._write_rows(buffer, rows)
        return buffer.getvalue().encode("utf-8")

    async def export_pages(
        self,
        db: AsyncSession,
        crawl_run_id: UUID,
        status_code: int | None = None,
    ) -> bytes:
        """
        Export crawl pages to CSV format.

        Args:
            db: Database session.
            crawl_run_id: Crawl run UUID.
            status_code: Optional filter by status code.

        Returns:
            CSV file contents as bytes.
        """
        # Build query
        query = select(CrawlPage).where(CrawlPage.crawl_run_id == crawl_run_id)

        if status_code is not None:
            query = query.where(CrawlPage.status_code == status_code)

        query = query.order_by(CrawlPage.url)

        result = await db.execute(query)
        pages = result.scalars().all()

        # Generate CSV
        buffer = io.StringIO()
        headers = [
            "URL",
            "Final URL",
            "Status Code",
            "Content Type",
            "Response Time (ms)",
            "Title",
            "Meta Description",
            "Canonical URL",
            "H1 Count",
            "First H1",
            "Word Count",
            "Render Mode",
        ]
        self._write_header(buffer, headers)

        rows = []
        for page in pages:
            rows.append([
                page.url,
                page.final_url or "",
                str(page.status_code) if page.status_code else "",
                page.content_type or "",
                str(page.response_time_ms) if page.response_time_ms else "",
                page.title or "",
                page.meta_description or "",
                page.canonical_url or "",
                str(page.h1_count) if page.h1_count else "",
                page.first_h1 or "",
                str(page.word_count) if page.word_count else "",
                page.render_mode or "",
            ])

        self._write_rows(buffer, rows)
        return buffer.getvalue().encode("utf-8")

    async def export_issues_streaming(
        self,
        db: AsyncSession,
        project_id: UUID,
        crawl_run_id: UUID | None = None,
        batch_size: int = 1000,
    ) -> AsyncIterator[bytes]:
        """
        Stream issues to CSV format for large datasets.

        Args:
            db: Database session.
            project_id: Project UUID.
            crawl_run_id: Optional crawl run filter.
            batch_size: Number of rows per batch.

        Yields:
            CSV chunks as bytes.
        """
        from semrush_core.models import CrawlRun, IssueType

        # Write header first
        buffer = io.StringIO()
        headers = [
            "URL",
            "Issue Type",
            "Category",
            "Severity",
            "Impact Score",
            "Confidence",
            "Evidence",
        ]
        self._write_header(buffer, headers)
        yield buffer.getvalue().encode("utf-8")

        # Build query
        query = (
            select(IssueInstance)
            .join(CrawlRun)
            .join(IssueType)
            .where(CrawlRun.project_id == project_id)
        )

        if crawl_run_id is not None:
            query = query.where(IssueInstance.crawl_run_id == crawl_run_id)

        query = query.order_by(IssueInstance.affected_url)

        # Stream in batches
        offset = 0
        while True:
            batch_query = query.offset(offset).limit(batch_size)
            result = await db.execute(batch_query)
            issues = result.scalars().all()

            if not issues:
                break

            buffer = io.StringIO()
            rows = []
            for issue in issues:
                issue_type = issue.issue_type
                rows.append([
                    issue.affected_url,
                    issue_type.id if issue_type else "",
                    issue_type.category if issue_type else "",
                    issue_type.severity if issue_type else "",
                    str(issue.impact_score) if issue.impact_score else "",
                    str(issue.confidence) if issue.confidence else "",
                    str(issue.evidence) if issue.evidence else "",
                ])

            self._write_rows(buffer, rows)
            yield buffer.getvalue().encode("utf-8")

            offset += batch_size

    async def export_backlinks_streaming(
        self,
        db: AsyncSession,
        project_id: UUID,
        batch_size: int = 1000,
    ) -> AsyncIterator[bytes]:
        """
        Stream backlinks to CSV format for large datasets.

        Args:
            db: Database session.
            project_id: Project UUID.
            batch_size: Number of rows per batch.

        Yields:
            CSV chunks as bytes.
        """
        # Write header first
        buffer = io.StringIO()
        headers = [
            "Source URL",
            "Source Domain",
            "Target URL",
            "Target Domain",
            "Anchor Text",
            "Rel Flags",
            "Source Type",
            "Discovered At",
        ]
        self._write_header(buffer, headers)
        yield buffer.getvalue().encode("utf-8")

        # Stream in batches
        offset = 0
        while True:
            query = (
                select(ProjectBacklink)
                .where(ProjectBacklink.project_id == project_id)
                .order_by(ProjectBacklink.source_domain, ProjectBacklink.source_url)
                .offset(offset)
                .limit(batch_size)
            )

            result = await db.execute(query)
            backlinks = result.scalars().all()

            if not backlinks:
                break

            buffer = io.StringIO()
            rows = []
            for bl in backlinks:
                rows.append([
                    bl.source_url,
                    bl.source_domain,
                    bl.target_url,
                    bl.target_domain,
                    bl.anchor or "",
                    ",".join(bl.rel_flags) if bl.rel_flags else "",
                    bl.source_type,
                    bl.discovered_at.isoformat() if bl.discovered_at else "",
                ])

            self._write_rows(buffer, rows)
            yield buffer.getvalue().encode("utf-8")

            offset += batch_size


def format_datetime(dt: datetime | None) -> str:
    """Format datetime for CSV export."""
    if dt is None:
        return ""
    return dt.isoformat()


def format_list(items: list[Any] | None) -> str:
    """Format list items as comma-separated string."""
    if items is None:
        return ""
    return ",".join(str(item) for item in items)
