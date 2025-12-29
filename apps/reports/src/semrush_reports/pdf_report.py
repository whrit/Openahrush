"""
PDF report service using WeasyPrint.

Provides PDF generation for:
- Site Audit reports
- Backlinks reports
- Full project reports
"""

from __future__ import annotations

import base64
import io
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from semrush_core.models import (
    CrawlPage,
    CrawlRun,
    IssueInstance,
    IssueType,
    Project,
    ProjectBacklink,
    Site,
)

# Template directory relative to this file
TEMPLATE_DIR = Path(__file__).parent / "templates"


class PDFRenderer:
    """
    PDF renderer using WeasyPrint and Jinja2 templates.

    Generates professional PDF reports from HTML templates
    with CSS styling and optional chart images.
    """

    def __init__(self, template_dir: Path | str | None = None) -> None:
        """
        Initialize PDF renderer.

        Args:
            template_dir: Path to template directory.
                         Defaults to package templates directory.
        """
        self.template_dir = Path(template_dir) if template_dir else TEMPLATE_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render_html(self, template_name: str, context: dict[str, Any]) -> str:
        """
        Render HTML from template.

        Args:
            template_name: Template file name.
            context: Template context data.

        Returns:
            Rendered HTML string.
        """
        template = self.env.get_template(template_name)
        return template.render(**context)

    def render_pdf(self, template_name: str, context: dict[str, Any]) -> bytes:
        """
        Render PDF from template.

        Args:
            template_name: Template file name.
            context: Template context data.

        Returns:
            PDF file contents as bytes.
        """
        try:
            from weasyprint import HTML
        except ImportError as e:
            raise ImportError(
                "WeasyPrint is required for PDF generation. "
                "Install with: pip install weasyprint"
            ) from e

        html_content = self.render_html(template_name, context)
        return HTML(string=html_content, base_url=str(self.template_dir)).write_pdf()


class ReportBuilder:
    """
    Builder for generating report context data from database.

    Collects and aggregates data for report templates.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize report builder.

        Args:
            db: Database session.
        """
        self.db = db

    async def build_audit_context(
        self,
        project_id: UUID,
        crawl_run_id: UUID | None = None,
        date_start: datetime | None = None,
        date_end: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Build context for audit report template.

        Args:
            project_id: Project UUID.
            crawl_run_id: Optional specific crawl run.
            date_start: Date range start.
            date_end: Date range end.

        Returns:
            Template context dictionary.
        """
        # Get project
        project_result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_result.scalar_one_or_none()

        if project is None:
            raise ValueError(f"Project {project_id} not found")

        # Get crawl run (latest if not specified)
        if crawl_run_id is None:
            crawl_result = await self.db.execute(
                select(CrawlRun)
                .where(CrawlRun.project_id == project_id)
                .order_by(CrawlRun.created_at.desc())
                .limit(1)
            )
            crawl_run = crawl_result.scalar_one_or_none()
        else:
            crawl_result = await self.db.execute(
                select(CrawlRun).where(CrawlRun.id == crawl_run_id)
            )
            crawl_run = crawl_result.scalar_one_or_none()

        if crawl_run is None:
            return self._empty_audit_context(project.name)

        # Get issues with types
        issues_result = await self.db.execute(
            select(IssueInstance, IssueType)
            .join(IssueType)
            .where(IssueInstance.crawl_run_id == crawl_run.id)
        )
        issues_with_types = issues_result.all()

        # Calculate severity summary
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0}
        issues_by_category: dict[str, int] = Counter()
        issues_by_type: dict[str, dict[str, Any]] = {}

        for issue, issue_type in issues_with_types:
            severity = issue_type.severity if issue_type else 0
            if severity >= 5:
                severity_counts["critical"] += 1
            elif severity >= 4:
                severity_counts["high"] += 1
            elif severity >= 3:
                severity_counts["medium"] += 1
            else:
                severity_counts["low"] += 1
            severity_counts["total"] += 1

            category = issue_type.category if issue_type else "unknown"
            issues_by_category[category] += 1

            type_id = issue_type.id if issue_type else "unknown"
            if type_id not in issues_by_type:
                issues_by_type[type_id] = {
                    "type": type_id,
                    "category": category,
                    "severity": severity,
                    "severity_label": self._severity_label(severity),
                    "count": 0,
                    "impact": 0,
                }
            issues_by_type[type_id]["count"] += 1
            if issue.impact_score:
                issues_by_type[type_id]["impact"] += float(issue.impact_score)

        # Sort top issues by count
        top_issues = sorted(
            issues_by_type.values(),
            key=lambda x: x["count"],
            reverse=True,
        )

        # Get page statistics
        pages_result = await self.db.execute(
            select(CrawlPage).where(CrawlPage.crawl_run_id == crawl_run.id)
        )
        pages = pages_result.scalars().all()

        # Calculate crawl stats
        pages_count = len(pages)
        pages_with_issues = len(
            {issue.crawl_page_id for issue, _ in issues_with_types}
        )
        response_times = [p.response_time_ms for p in pages if p.response_time_ms]
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        error_pages = sum(1 for p in pages if p.status_code and p.status_code >= 400)
        error_rate = (error_pages / pages_count * 100) if pages_count > 0 else 0

        # Status code distribution
        status_counter: Counter = Counter()
        for page in pages:
            if page.status_code:
                status_counter[page.status_code] += 1

        status_codes = [
            {
                "code": code,
                "description": self._status_description(code),
                "count": count,
                "percentage": count / pages_count * 100 if pages_count > 0 else 0,
            }
            for code, count in status_counter.most_common()
        ]

        # Affected URLs
        url_issues: dict[str, dict[str, int]] = {}
        for issue, issue_type in issues_with_types:
            url = issue.affected_url
            if url not in url_issues:
                url_issues[url] = {"total_issues": 0, "critical": 0, "high": 0}
            url_issues[url]["total_issues"] += 1
            severity = issue_type.severity if issue_type else 0
            if severity >= 5:
                url_issues[url]["critical"] += 1
            elif severity >= 4:
                url_issues[url]["high"] += 1

        affected_urls = sorted(
            [{"url": url, **counts} for url, counts in url_issues.items()],
            key=lambda x: x["total_issues"],
            reverse=True,
        )

        return {
            "project_name": project.name,
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "date_range": {
                "start": (date_start or crawl_run.created_at).strftime("%Y-%m-%d"),
                "end": (date_end or datetime.now(UTC)).strftime("%Y-%m-%d"),
            },
            "issues_summary": severity_counts,
            "issues_by_category": dict(issues_by_category),
            "top_issues": top_issues,
            "affected_urls": affected_urls,
            "crawl_stats": {
                "pages_crawled": pages_count,
                "pages_with_issues": pages_with_issues,
                "avg_response_time": round(avg_response),
                "error_rate": round(error_rate, 1),
            },
            "status_codes": status_codes,
            "recommendations": self._generate_recommendations(severity_counts, top_issues),
        }

    async def build_backlinks_context(
        self,
        project_id: UUID,
    ) -> dict[str, Any]:
        """
        Build context for backlinks report template.

        Args:
            project_id: Project UUID.

        Returns:
            Template context dictionary.
        """
        # Get project
        project_result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_result.scalar_one_or_none()

        if project is None:
            raise ValueError(f"Project {project_id} not found")

        # Get all backlinks
        backlinks_result = await self.db.execute(
            select(ProjectBacklink).where(ProjectBacklink.project_id == project_id)
        )
        backlinks = backlinks_result.scalars().all()

        if not backlinks:
            return self._empty_backlinks_context(project.name)

        # Calculate summary
        total = len(backlinks)
        dofollow = sum(1 for bl in backlinks if bl.is_dofollow)
        nofollow = sum(1 for bl in backlinks if bl.is_nofollow)
        ugc = sum(1 for bl in backlinks if bl.is_ugc)
        sponsored = sum(1 for bl in backlinks if bl.is_sponsored)
        referring_domains = len({bl.source_domain for bl in backlinks})

        # Group by source type
        backlinks_by_source = Counter(bl.source_type for bl in backlinks)

        # Top referring domains
        domain_stats: dict[str, dict[str, Any]] = {}
        for bl in backlinks:
            domain = bl.source_domain
            if domain not in domain_stats:
                domain_stats[domain] = {
                    "domain": domain,
                    "backlinks": 0,
                    "dofollow": 0,
                    "first_seen": bl.discovered_at,
                }
            domain_stats[domain]["backlinks"] += 1
            if bl.is_dofollow:
                domain_stats[domain]["dofollow"] += 1
            if bl.discovered_at and (
                domain_stats[domain]["first_seen"] is None
                or bl.discovered_at < domain_stats[domain]["first_seen"]
            ):
                domain_stats[domain]["first_seen"] = bl.discovered_at

        top_domains = sorted(
            [
                {
                    **d,
                    "first_seen": d["first_seen"].strftime("%Y-%m-%d")
                    if d["first_seen"]
                    else "-",
                }
                for d in domain_stats.values()
            ],
            key=lambda x: x["backlinks"],
            reverse=True,
        )

        # Top anchor texts
        anchor_counter: Counter = Counter()
        for bl in backlinks:
            anchor_counter[bl.anchor or ""] += 1

        top_anchors = [
            {
                "text": anchor,
                "count": count,
                "percentage": count / total * 100,
            }
            for anchor, count in anchor_counter.most_common(20)
        ]

        # Top target URLs
        target_stats: dict[str, dict[str, Any]] = {}
        for bl in backlinks:
            target = bl.target_url
            if target not in target_stats:
                target_stats[target] = {
                    "url": target,
                    "backlinks": 0,
                    "domains": set(),
                }
            target_stats[target]["backlinks"] += 1
            target_stats[target]["domains"].add(bl.source_domain)

        top_targets = sorted(
            [
                {"url": t["url"], "backlinks": t["backlinks"], "domains": len(t["domains"])}
                for t in target_stats.values()
            ],
            key=lambda x: x["backlinks"],
            reverse=True,
        )

        # New backlinks (last 30 days)
        thirty_days_ago = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        new_backlinks = [
            {
                "source_url": bl.source_url,
                "target_url": bl.target_url,
                "anchor": bl.anchor,
                "discovered_at": bl.discovered_at.strftime("%Y-%m-%d")
                if bl.discovered_at
                else "-",
            }
            for bl in sorted(backlinks, key=lambda x: x.discovered_at or datetime.min, reverse=True)[:20]
        ]

        return {
            "project_name": project.name,
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "summary": {
                "total_backlinks": total,
                "referring_domains": referring_domains,
                "dofollow_links": dofollow,
                "nofollow_links": nofollow,
            },
            "distribution": {
                "dofollow_pct": dofollow / total * 100 if total > 0 else 0,
                "nofollow_pct": nofollow / total * 100 if total > 0 else 0,
                "ugc_pct": ugc / total * 100 if total > 0 else 0,
                "sponsored_pct": sponsored / total * 100 if total > 0 else 0,
            },
            "backlinks_by_source": dict(backlinks_by_source),
            "top_referring_domains": top_domains,
            "top_anchor_texts": top_anchors,
            "top_target_urls": top_targets,
            "new_backlinks": new_backlinks,
        }

    def _empty_audit_context(self, project_name: str) -> dict[str, Any]:
        """Return empty audit context when no data available."""
        return {
            "project_name": project_name,
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "date_range": {"start": "-", "end": "-"},
            "issues_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0},
            "issues_by_category": {},
            "top_issues": [],
            "affected_urls": [],
            "crawl_stats": {
                "pages_crawled": 0,
                "pages_with_issues": 0,
                "avg_response_time": 0,
                "error_rate": 0,
            },
            "status_codes": [],
            "recommendations": [],
        }

    def _empty_backlinks_context(self, project_name: str) -> dict[str, Any]:
        """Return empty backlinks context when no data available."""
        return {
            "project_name": project_name,
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "summary": {
                "total_backlinks": 0,
                "referring_domains": 0,
                "dofollow_links": 0,
                "nofollow_links": 0,
            },
            "distribution": {
                "dofollow_pct": 0,
                "nofollow_pct": 0,
                "ugc_pct": 0,
                "sponsored_pct": 0,
            },
            "backlinks_by_source": {},
            "top_referring_domains": [],
            "top_anchor_texts": [],
            "top_target_urls": [],
            "new_backlinks": [],
        }

    def _severity_label(self, severity: int) -> str:
        """Convert severity number to label."""
        labels = {5: "Critical", 4: "High", 3: "Medium", 2: "Low", 1: "Info"}
        return labels.get(severity, "Unknown")

    def _status_description(self, status_code: int) -> str:
        """Get HTTP status code description."""
        descriptions = {
            200: "OK",
            201: "Created",
            301: "Moved Permanently",
            302: "Found (Redirect)",
            304: "Not Modified",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            410: "Gone",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable",
        }
        return descriptions.get(status_code, f"HTTP {status_code}")

    def _generate_recommendations(
        self,
        severity_counts: dict[str, int],
        top_issues: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """Generate recommendations based on issues."""
        recommendations = []

        if severity_counts["critical"] > 0:
            recommendations.append({
                "title": "Address Critical Issues Immediately",
                "description": (
                    f"You have {severity_counts['critical']} critical issues that "
                    "require immediate attention. These can severely impact SEO "
                    "and user experience."
                ),
            })

        if severity_counts["high"] > 10:
            recommendations.append({
                "title": "Prioritize High-Severity Issues",
                "description": (
                    f"There are {severity_counts['high']} high-severity issues. "
                    "Schedule time to address these in the next sprint."
                ),
            })

        # Check for specific issue types
        for issue in top_issues[:5]:
            if "broken" in issue["type"].lower() or "404" in issue["type"]:
                recommendations.append({
                    "title": "Fix Broken Links",
                    "description": (
                        f"Found {issue['count']} broken link issues. "
                        "Implement redirects or remove dead links."
                    ),
                })
                break

        for issue in top_issues[:5]:
            if "title" in issue["type"].lower() and "missing" in issue["type"].lower():
                recommendations.append({
                    "title": "Add Missing Title Tags",
                    "description": (
                        "Pages without title tags hurt SEO rankings. "
                        "Ensure every page has a unique, descriptive title."
                    ),
                })
                break

        for issue in top_issues[:5]:
            if "meta" in issue["type"].lower() and "description" in issue["type"].lower():
                recommendations.append({
                    "title": "Write Meta Descriptions",
                    "description": (
                        "Meta descriptions improve click-through rates in search results. "
                        "Write compelling descriptions for key pages."
                    ),
                })
                break

        return recommendations[:5]


class PDFReportService:
    """
    High-level service for generating PDF reports.

    Combines report building and PDF rendering.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize PDF report service.

        Args:
            db: Database session.
        """
        self.db = db
        self.builder = ReportBuilder(db)
        self.renderer = PDFRenderer()

    async def generate_audit_report(
        self,
        project_id: UUID,
        crawl_run_id: UUID | None = None,
    ) -> bytes:
        """
        Generate site audit PDF report.

        Args:
            project_id: Project UUID.
            crawl_run_id: Optional specific crawl run.

        Returns:
            PDF file contents as bytes.
        """
        context = await self.builder.build_audit_context(project_id, crawl_run_id)
        return self.renderer.render_pdf("audit_report.html", context)

    async def generate_backlinks_report(
        self,
        project_id: UUID,
    ) -> bytes:
        """
        Generate backlinks PDF report.

        Args:
            project_id: Project UUID.

        Returns:
            PDF file contents as bytes.
        """
        context = await self.builder.build_backlinks_context(project_id)
        return self.renderer.render_pdf("backlinks_report.html", context)

    async def generate_full_report(
        self,
        project_id: UUID,
        crawl_run_id: UUID | None = None,
    ) -> bytes:
        """
        Generate full project PDF report.

        Combines audit and backlinks reports.

        Args:
            project_id: Project UUID.
            crawl_run_id: Optional specific crawl run.

        Returns:
            PDF file contents as bytes.
        """
        # For MVP, generate audit report
        # Full report combining multiple sections can be added later
        return await self.generate_audit_report(project_id, crawl_run_id)
