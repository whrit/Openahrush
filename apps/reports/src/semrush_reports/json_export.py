"""
JSON export service for generating JSON exports.

Provides JSON generation with streaming support for:
- Issues export
- Backlinks export
- Crawl pages export
- Full project export
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from semrush_core.models import CrawlPage, IssueInstance, Project, ProjectBacklink


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for SQLAlchemy models and special types."""

    def default(self, obj: Any) -> Any:
        """Encode special types to JSON-serializable format."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return super().default(obj)


class JSONExporter:
    """
    JSON export generator with streaming support.

    Generates JSON files with proper structure and supports
    streaming (JSON Lines format) for large datasets.
    """

    def __init__(self, pretty: bool = False) -> None:
        """
        Initialize JSON exporter.

        Args:
            pretty: Whether to format JSON with indentation.
        """
        self.pretty = pretty
        self.indent = 2 if pretty else None

    def _dumps(self, data: Any) -> str:
        """Serialize data to JSON string."""
        return json.dumps(data, cls=JSONEncoder, indent=self.indent, ensure_ascii=False)

    async def export_issues(
        self,
        db: AsyncSession,
        project_id: UUID,
        crawl_run_id: UUID | None = None,
        severity_min: int | None = None,
    ) -> bytes:
        """
        Export issues to JSON format.

        Args:
            db: Database session.
            project_id: Project UUID.
            crawl_run_id: Optional crawl run filter.
            severity_min: Minimum severity level filter.

        Returns:
            JSON file contents as bytes.
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

        # Build export data
        export_data = {
            "export_type": "issues",
            "project_id": str(project_id),
            "crawl_run_id": str(crawl_run_id) if crawl_run_id else None,
            "exported_at": datetime.utcnow().isoformat(),
            "total_count": len(issues),
            "items": [],
        }

        for issue in issues:
            issue_type = issue.issue_type
            export_data["items"].append({
                "id": str(issue.id),
                "url": issue.affected_url,
                "issue_type": {
                    "id": issue_type.id if issue_type else None,
                    "category": issue_type.category if issue_type else None,
                    "severity": issue_type.severity if issue_type else None,
                    "description": issue_type.description if issue_type else None,
                },
                "impact_score": float(issue.impact_score) if issue.impact_score else None,
                "confidence": float(issue.confidence) if issue.confidence else None,
                "evidence": issue.evidence,
            })

        return self._dumps(export_data).encode("utf-8")

    async def export_backlinks(
        self,
        db: AsyncSession,
        project_id: UUID,
        source_type: str | None = None,
        source_domain: str | None = None,
    ) -> bytes:
        """
        Export backlinks to JSON format.

        Args:
            db: Database session.
            project_id: Project UUID.
            source_type: Optional filter by source type.
            source_domain: Optional filter by source domain.

        Returns:
            JSON file contents as bytes.
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

        # Build export data
        export_data = {
            "export_type": "backlinks",
            "project_id": str(project_id),
            "exported_at": datetime.utcnow().isoformat(),
            "total_count": len(backlinks),
            "items": [],
        }

        for bl in backlinks:
            export_data["items"].append({
                "id": str(bl.id),
                "source_url": bl.source_url,
                "source_domain": bl.source_domain,
                "target_url": bl.target_url,
                "target_domain": bl.target_domain,
                "anchor": bl.anchor,
                "rel_flags": bl.rel_flags,
                "source_type": bl.source_type,
                "discovered_at": bl.discovered_at.isoformat() if bl.discovered_at else None,
            })

        return self._dumps(export_data).encode("utf-8")

    async def export_pages(
        self,
        db: AsyncSession,
        crawl_run_id: UUID,
        status_code: int | None = None,
    ) -> bytes:
        """
        Export crawl pages to JSON format.

        Args:
            db: Database session.
            crawl_run_id: Crawl run UUID.
            status_code: Optional filter by status code.

        Returns:
            JSON file contents as bytes.
        """
        # Build query
        query = select(CrawlPage).where(CrawlPage.crawl_run_id == crawl_run_id)

        if status_code is not None:
            query = query.where(CrawlPage.status_code == status_code)

        query = query.order_by(CrawlPage.url)

        result = await db.execute(query)
        pages = result.scalars().all()

        # Build export data
        export_data = {
            "export_type": "pages",
            "crawl_run_id": str(crawl_run_id),
            "exported_at": datetime.utcnow().isoformat(),
            "total_count": len(pages),
            "items": [],
        }

        for page in pages:
            export_data["items"].append({
                "id": str(page.id),
                "url": page.url,
                "final_url": page.final_url,
                "status_code": page.status_code,
                "content_type": page.content_type,
                "response_time_ms": page.response_time_ms,
                "title": page.title,
                "meta_description": page.meta_description,
                "canonical_url": page.canonical_url,
                "meta_robots": page.meta_robots,
                "h1_count": page.h1_count,
                "first_h1": page.first_h1,
                "word_count": page.word_count,
                "text_length": page.text_length,
                "render_mode": page.render_mode,
                "was_rendered": page.was_rendered,
            })

        return self._dumps(export_data).encode("utf-8")

    async def export_issues_jsonl(
        self,
        db: AsyncSession,
        project_id: UUID,
        crawl_run_id: UUID | None = None,
        batch_size: int = 1000,
    ) -> AsyncIterator[bytes]:
        """
        Stream issues as JSON Lines format for large datasets.

        Args:
            db: Database session.
            project_id: Project UUID.
            crawl_run_id: Optional crawl run filter.
            batch_size: Number of rows per batch.

        Yields:
            JSON Lines as bytes (one JSON object per line).
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

        query = query.order_by(IssueInstance.affected_url)

        # Stream in batches
        offset = 0
        while True:
            batch_query = query.offset(offset).limit(batch_size)
            result = await db.execute(batch_query)
            issues = result.scalars().all()

            if not issues:
                break

            lines = []
            for issue in issues:
                issue_type = issue.issue_type
                data = {
                    "id": str(issue.id),
                    "url": issue.affected_url,
                    "issue_type_id": issue_type.id if issue_type else None,
                    "category": issue_type.category if issue_type else None,
                    "severity": issue_type.severity if issue_type else None,
                    "impact_score": float(issue.impact_score) if issue.impact_score else None,
                    "confidence": float(issue.confidence) if issue.confidence else None,
                    "evidence": issue.evidence,
                }
                lines.append(json.dumps(data, cls=JSONEncoder, ensure_ascii=False))

            yield ("\n".join(lines) + "\n").encode("utf-8")
            offset += batch_size

    async def export_backlinks_jsonl(
        self,
        db: AsyncSession,
        project_id: UUID,
        batch_size: int = 1000,
    ) -> AsyncIterator[bytes]:
        """
        Stream backlinks as JSON Lines format for large datasets.

        Args:
            db: Database session.
            project_id: Project UUID.
            batch_size: Number of rows per batch.

        Yields:
            JSON Lines as bytes (one JSON object per line).
        """
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

            lines = []
            for bl in backlinks:
                data = {
                    "id": str(bl.id),
                    "source_url": bl.source_url,
                    "source_domain": bl.source_domain,
                    "target_url": bl.target_url,
                    "target_domain": bl.target_domain,
                    "anchor": bl.anchor,
                    "rel_flags": bl.rel_flags,
                    "source_type": bl.source_type,
                    "discovered_at": bl.discovered_at.isoformat() if bl.discovered_at else None,
                }
                lines.append(json.dumps(data, cls=JSONEncoder, ensure_ascii=False))

            yield ("\n".join(lines) + "\n").encode("utf-8")
            offset += batch_size

    async def export_full_report(
        self,
        db: AsyncSession,
        project_id: UUID,
        crawl_run_id: UUID | None = None,
    ) -> bytes:
        """
        Export full project report with all data.

        Args:
            db: Database session.
            project_id: Project UUID.
            crawl_run_id: Optional specific crawl run.

        Returns:
            JSON file contents as bytes.
        """
        from semrush_core.models import CrawlRun, IssueType, Site

        # Get project
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()

        if project is None:
            raise ValueError(f"Project {project_id} not found")

        # Get sites
        sites_result = await db.execute(select(Site).where(Site.project_id == project_id))
        sites = sites_result.scalars().all()

        # Get latest crawl run if not specified
        if crawl_run_id is None:
            crawl_result = await db.execute(
                select(CrawlRun)
                .where(CrawlRun.project_id == project_id)
                .order_by(CrawlRun.created_at.desc())
                .limit(1)
            )
            crawl_run = crawl_result.scalar_one_or_none()
            crawl_run_id = crawl_run.id if crawl_run else None

        # Build full export
        export_data = {
            "export_type": "full_report",
            "exported_at": datetime.utcnow().isoformat(),
            "project": {
                "id": str(project.id),
                "name": project.name,
                "created_at": project.created_at.isoformat() if project.created_at else None,
            },
            "sites": [
                {
                    "id": str(site.id),
                    "domain": site.domain,
                    "base_url": site.base_url,
                }
                for site in sites
            ],
            "crawl_run_id": str(crawl_run_id) if crawl_run_id else None,
            "issues": [],
            "backlinks": [],
            "pages": [],
        }

        # Get issues if we have a crawl run
        if crawl_run_id:
            issues_result = await db.execute(
                select(IssueInstance)
                .join(IssueType)
                .where(IssueInstance.crawl_run_id == crawl_run_id)
                .order_by(IssueInstance.affected_url)
                .limit(10000)  # Limit for full report
            )
            issues = issues_result.scalars().all()

            for issue in issues:
                issue_type = issue.issue_type
                export_data["issues"].append({
                    "id": str(issue.id),
                    "url": issue.affected_url,
                    "issue_type_id": issue_type.id if issue_type else None,
                    "category": issue_type.category if issue_type else None,
                    "severity": issue_type.severity if issue_type else None,
                    "impact_score": float(issue.impact_score) if issue.impact_score else None,
                })

            # Get pages
            pages_result = await db.execute(
                select(CrawlPage)
                .where(CrawlPage.crawl_run_id == crawl_run_id)
                .order_by(CrawlPage.url)
                .limit(10000)
            )
            pages = pages_result.scalars().all()

            for page in pages:
                export_data["pages"].append({
                    "id": str(page.id),
                    "url": page.url,
                    "status_code": page.status_code,
                    "title": page.title,
                    "word_count": page.word_count,
                })

        # Get backlinks (limited)
        backlinks_result = await db.execute(
            select(ProjectBacklink)
            .where(ProjectBacklink.project_id == project_id)
            .order_by(ProjectBacklink.source_domain)
            .limit(10000)
        )
        backlinks = backlinks_result.scalars().all()

        for bl in backlinks:
            export_data["backlinks"].append({
                "id": str(bl.id),
                "source_url": bl.source_url,
                "source_domain": bl.source_domain,
                "target_url": bl.target_url,
                "anchor": bl.anchor,
            })

        export_data["summary"] = {
            "total_issues": len(export_data["issues"]),
            "total_pages": len(export_data["pages"]),
            "total_backlinks": len(export_data["backlinks"]),
        }

        return self._dumps(export_data).encode("utf-8")
