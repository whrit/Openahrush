"""
Report context builders for PDF reports.

Provides async functions to build template context data
from database queries for various report types.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from semrush_core.models import (
    CrawlPage,
    CrawlRun,
    IssueInstance,
    IssueType,
    Project,
    ProjectBacklink,
    SearchFactDaily,
)


async def build_audit_context(
    db: AsyncSession,
    project_id: UUID,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build context for audit report template.

    Args:
        db: Database session.
        project_id: Project UUID.
        params: Optional parameters including:
            - crawl_run_id: Specific crawl run UUID
            - date_start: Start date for date range
            - date_end: End date for date range

    Returns:
        Template context dictionary with:
            - project_name: Project name
            - generated_at: Generation timestamp
            - date_range: Start and end dates
            - issues_summary: Severity counts
            - issues_by_category: Category counts
            - top_issues: Top issues by count
            - affected_urls: URLs with most issues
            - crawl_stats: Crawl statistics
            - status_codes: HTTP status code distribution
            - recommendations: Generated recommendations
    """
    params = params or {}
    crawl_run_id = params.get("crawl_run_id")
    date_start = params.get("date_start")
    date_end = params.get("date_end")

    # Get project
    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()

    if project is None:
        raise ValueError(f"Project {project_id} not found")

    # Get crawl run (latest if not specified)
    if crawl_run_id is None:
        crawl_result = await db.execute(
            select(CrawlRun)
            .where(CrawlRun.project_id == project_id)
            .order_by(CrawlRun.created_at.desc())
            .limit(1)
        )
        crawl_run = crawl_result.scalar_one_or_none()
    else:
        crawl_result = await db.execute(
            select(CrawlRun).where(CrawlRun.id == crawl_run_id)
        )
        crawl_run = crawl_result.scalar_one_or_none()

    if crawl_run is None:
        return _empty_audit_context(project.name)

    # Get issues with types
    issues_result = await db.execute(
        select(IssueInstance, IssueType)
        .join(IssueType)
        .where(IssueInstance.crawl_run_id == crawl_run.id)
    )
    issues_with_types = issues_result.all()

    # Calculate severity summary
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0}
    issues_by_category: Counter[str] = Counter()
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
                "severity_label": _severity_label(severity),
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
    pages_result = await db.execute(
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
    status_counter: Counter[int] = Counter()
    for page in pages:
        if page.status_code:
            status_counter[page.status_code] += 1

    status_codes = [
        {
            "code": code,
            "description": _status_description(code),
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
        "recommendations": _generate_audit_recommendations(severity_counts, top_issues),
    }


async def build_performance_context(
    db: AsyncSession,
    project_id: UUID,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build context for performance report template.

    Args:
        db: Database session.
        project_id: Project UUID.
        params: Optional parameters including:
            - date_start: Start date for date range
            - date_end: End date for date range
            - engine: Search engine filter ('google', 'bing')
            - include_charts: Whether to include chart data

    Returns:
        Template context dictionary with:
            - project_name: Project name
            - generated_at: Generation timestamp
            - date_range: Start and end dates
            - summary: Total clicks, impressions, CTR, position
            - trends: Period-over-period comparisons
            - top_queries: Top performing queries
            - top_pages: Top performing pages
            - top_countries: Traffic by country
            - devices: Traffic by device type
            - rising_queries: Queries with growth
            - declining_queries: Queries with decline
            - recommendations: Performance recommendations
    """
    params = params or {}
    date_end = params.get("date_end") or datetime.now(UTC).date()
    date_start = params.get("date_start") or (date_end - timedelta(days=30))
    engine = params.get("engine")

    # Get project
    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()

    if project is None:
        raise ValueError(f"Project {project_id} not found")

    # Build base query
    base_query = select(SearchFactDaily).where(
        and_(
            SearchFactDaily.project_id == project_id,
            SearchFactDaily.date >= date_start,
            SearchFactDaily.date <= date_end,
        )
    )

    if engine:
        base_query = base_query.where(SearchFactDaily.engine == engine)

    # Get all facts for the period
    facts_result = await db.execute(base_query)
    facts = facts_result.scalars().all()

    if not facts:
        return _empty_performance_context(project.name, date_start, date_end)

    # Calculate summary
    total_clicks = sum(f.clicks for f in facts)
    total_impressions = sum(f.impressions for f in facts)
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    positions = [float(f.avg_position) for f in facts if f.avg_position]
    avg_position = sum(positions) / len(positions) if positions else 0

    # Get previous period for trends
    period_days = (date_end - date_start).days
    prev_end = date_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days)

    prev_query = select(SearchFactDaily).where(
        and_(
            SearchFactDaily.project_id == project_id,
            SearchFactDaily.date >= prev_start,
            SearchFactDaily.date <= prev_end,
        )
    )
    if engine:
        prev_query = prev_query.where(SearchFactDaily.engine == engine)

    prev_result = await db.execute(prev_query)
    prev_facts = prev_result.scalars().all()

    prev_clicks = sum(f.clicks for f in prev_facts)
    prev_impressions = sum(f.impressions for f in prev_facts)
    prev_ctr = (prev_clicks / prev_impressions * 100) if prev_impressions > 0 else 0
    prev_positions = [float(f.avg_position) for f in prev_facts if f.avg_position]
    prev_avg_position = sum(prev_positions) / len(prev_positions) if prev_positions else 0

    trends = {
        "clicks_change": _percent_change(prev_clicks, total_clicks),
        "impressions_change": _percent_change(prev_impressions, total_impressions),
        "ctr_change": avg_ctr - prev_ctr,
        "position_change": avg_position - prev_avg_position,
    }

    # Top queries
    query_stats: dict[str, dict[str, Any]] = {}
    for f in facts:
        if f.query:
            if f.query not in query_stats:
                query_stats[f.query] = {
                    "query": f.query,
                    "clicks": 0,
                    "impressions": 0,
                    "positions": [],
                }
            query_stats[f.query]["clicks"] += f.clicks
            query_stats[f.query]["impressions"] += f.impressions
            if f.avg_position:
                query_stats[f.query]["positions"].append(float(f.avg_position))

    top_queries = []
    for q in query_stats.values():
        imp = q["impressions"]
        pos_list = q["positions"]
        top_queries.append({
            "query": q["query"],
            "clicks": q["clicks"],
            "impressions": imp,
            "ctr": (q["clicks"] / imp * 100) if imp > 0 else 0,
            "position": sum(pos_list) / len(pos_list) if pos_list else 0,
        })
    top_queries.sort(key=lambda x: x["clicks"], reverse=True)

    # Top pages
    page_stats: dict[str, dict[str, Any]] = {}
    for f in facts:
        if f.page_url:
            if f.page_url not in page_stats:
                page_stats[f.page_url] = {
                    "url": f.page_url,
                    "clicks": 0,
                    "impressions": 0,
                    "positions": [],
                }
            page_stats[f.page_url]["clicks"] += f.clicks
            page_stats[f.page_url]["impressions"] += f.impressions
            if f.avg_position:
                page_stats[f.page_url]["positions"].append(float(f.avg_position))

    top_pages = []
    for p in page_stats.values():
        imp = p["impressions"]
        pos_list = p["positions"]
        top_pages.append({
            "url": p["url"],
            "clicks": p["clicks"],
            "impressions": imp,
            "ctr": (p["clicks"] / imp * 100) if imp > 0 else 0,
            "position": sum(pos_list) / len(pos_list) if pos_list else 0,
        })
    top_pages.sort(key=lambda x: x["clicks"], reverse=True)

    # Top countries
    country_stats: dict[str, dict[str, Any]] = {}
    for f in facts:
        if f.country:
            if f.country not in country_stats:
                country_stats[f.country] = {
                    "country": f.country,
                    "clicks": 0,
                    "impressions": 0,
                }
            country_stats[f.country]["clicks"] += f.clicks
            country_stats[f.country]["impressions"] += f.impressions

    top_countries = []
    for c in country_stats.values():
        imp = c["impressions"]
        top_countries.append({
            "country": c["country"],
            "clicks": c["clicks"],
            "impressions": imp,
            "ctr": (c["clicks"] / imp * 100) if imp > 0 else 0,
        })
    top_countries.sort(key=lambda x: x["clicks"], reverse=True)

    # Device breakdown
    device_stats: dict[str, dict[str, Any]] = {}
    for f in facts:
        device = f.device or "unknown"
        if device not in device_stats:
            device_stats[device] = {"device": device, "clicks": 0, "impressions": 0}
        device_stats[device]["clicks"] += f.clicks
        device_stats[device]["impressions"] += f.impressions

    devices = []
    for d in device_stats.values():
        imp = d["impressions"]
        devices.append({
            "device": d["device"],
            "clicks": d["clicks"],
            "impressions": imp,
            "ctr": (d["clicks"] / imp * 100) if imp > 0 else 0,
        })
    devices.sort(key=lambda x: x["clicks"], reverse=True)

    # Calculate rising/declining queries (compare to previous period)
    prev_query_stats: dict[str, dict[str, int]] = {}
    for f in prev_facts:
        if f.query:
            if f.query not in prev_query_stats:
                prev_query_stats[f.query] = {"clicks": 0}
            prev_query_stats[f.query]["clicks"] += f.clicks

    rising_queries = []
    declining_queries = []
    for q in top_queries[:50]:
        prev_clicks = prev_query_stats.get(q["query"], {}).get("clicks", 0)
        if prev_clicks > 0:
            change = _percent_change(prev_clicks, q["clicks"])
            if change > 20:  # Significant growth
                rising_queries.append({
                    "query": q["query"],
                    "clicks": q["clicks"],
                    "growth": change,
                })
            elif change < -20:  # Significant decline
                declining_queries.append({
                    "query": q["query"],
                    "clicks": q["clicks"],
                    "change": change,
                })

    rising_queries.sort(key=lambda x: x["growth"], reverse=True)
    declining_queries.sort(key=lambda x: x["change"])

    return {
        "project_name": project.name,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "date_range": {
            "start": date_start.strftime("%Y-%m-%d")
            if hasattr(date_start, "strftime")
            else str(date_start),
            "end": date_end.strftime("%Y-%m-%d")
            if hasattr(date_end, "strftime")
            else str(date_end),
        },
        "summary": {
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "avg_ctr": avg_ctr,
            "avg_position": avg_position,
        },
        "trends": trends,
        "top_queries": top_queries,
        "top_pages": top_pages,
        "top_countries": top_countries,
        "devices": devices,
        "rising_queries": rising_queries,
        "declining_queries": declining_queries,
        "recommendations": _generate_performance_recommendations(
            total_clicks, avg_ctr, avg_position, trends, top_queries
        ),
    }


async def build_backlinks_context(
    db: AsyncSession,
    project_id: UUID,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build context for backlinks report template.

    Args:
        db: Database session.
        project_id: Project UUID.
        params: Optional parameters (reserved for future use).

    Returns:
        Template context dictionary with:
            - project_name: Project name
            - generated_at: Generation timestamp
            - summary: Total backlinks, domains, dofollow/nofollow counts
            - distribution: Link type percentages
            - backlinks_by_source: Backlinks grouped by source type
            - top_referring_domains: Top referring domains
            - top_anchor_texts: Most common anchor texts
            - top_target_urls: Most linked pages
            - new_backlinks: Recently discovered backlinks
    """
    params = params or {}

    # Get project
    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()

    if project is None:
        raise ValueError(f"Project {project_id} not found")

    # Get all backlinks
    backlinks_result = await db.execute(
        select(ProjectBacklink).where(ProjectBacklink.project_id == project_id)
    )
    backlinks = backlinks_result.scalars().all()

    if not backlinks:
        return _empty_backlinks_context(project.name)

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
    anchor_counter: Counter[str] = Counter()
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

    # New backlinks (sorted by discovered_at)
    sorted_backlinks = sorted(
        backlinks,
        key=lambda x: x.discovered_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
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
        for bl in sorted_backlinks[:20]
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


async def build_overview_context(
    db: AsyncSession,
    project_id: UUID,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build context for overview report template.

    Combines audit, backlinks, and performance data into a single report.

    Args:
        db: Database session.
        project_id: Project UUID.
        params: Optional parameters.

    Returns:
        Template context dictionary with combined data.
    """
    params = params or {}

    # Get project
    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()

    if project is None:
        raise ValueError(f"Project {project_id} not found")

    # Build individual contexts
    audit_ctx = await build_audit_context(db, project_id, params)
    backlinks_ctx = await build_backlinks_context(db, project_id, params)
    performance_ctx = await build_performance_context(db, project_id, params)

    # Calculate health score
    health_score = _calculate_health_score(audit_ctx, backlinks_ctx, performance_ctx)

    # Combine into overview context
    return {
        "project_name": project.name,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "date_range": audit_ctx["date_range"],
        "health_score": health_score,
        "audit": {
            "critical": audit_ctx["issues_summary"]["critical"],
            "high": audit_ctx["issues_summary"]["high"],
            "medium": audit_ctx["issues_summary"]["medium"],
            "low": audit_ctx["issues_summary"]["low"],
            "issues_total": audit_ctx["issues_summary"]["total"],
            "top_issues": audit_ctx["top_issues"][:5],
        },
        "backlinks": {
            "total_backlinks": backlinks_ctx["summary"]["total_backlinks"],
            "referring_domains": backlinks_ctx["summary"]["referring_domains"],
            "dofollow_pct": backlinks_ctx["distribution"]["dofollow_pct"],
            "new_this_month": len(backlinks_ctx["new_backlinks"]),
            "top_domains": backlinks_ctx["top_referring_domains"][:5],
        },
        "performance": {
            "total_clicks": performance_ctx["summary"]["total_clicks"],
            "total_impressions": performance_ctx["summary"]["total_impressions"],
            "avg_ctr": performance_ctx["summary"]["avg_ctr"],
            "avg_position": performance_ctx["summary"]["avg_position"],
            "top_queries": performance_ctx["top_queries"][:10],
        },
        "crawl_stats": audit_ctx["crawl_stats"],
        "recommendations": _generate_overview_recommendations(
            audit_ctx, backlinks_ctx, performance_ctx
        ),
        "action_items": _generate_action_items(
            audit_ctx, backlinks_ctx, performance_ctx
        ),
    }


# Helper functions


def _empty_audit_context(project_name: str) -> dict[str, Any]:
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


def _empty_performance_context(
    project_name: str,
    date_start: Any,
    date_end: Any,
) -> dict[str, Any]:
    """Return empty performance context when no data available."""
    return {
        "project_name": project_name,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "date_range": {
            "start": date_start.strftime("%Y-%m-%d")
            if hasattr(date_start, "strftime")
            else str(date_start),
            "end": date_end.strftime("%Y-%m-%d")
            if hasattr(date_end, "strftime")
            else str(date_end),
        },
        "summary": {
            "total_clicks": 0,
            "total_impressions": 0,
            "avg_ctr": 0,
            "avg_position": 0,
        },
        "trends": {
            "clicks_change": 0,
            "impressions_change": 0,
            "ctr_change": 0,
            "position_change": 0,
        },
        "top_queries": [],
        "top_pages": [],
        "top_countries": [],
        "devices": [],
        "rising_queries": [],
        "declining_queries": [],
        "recommendations": [],
    }


def _empty_backlinks_context(project_name: str) -> dict[str, Any]:
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


def _severity_label(severity: int) -> str:
    """Convert severity number to label."""
    labels = {5: "Critical", 4: "High", 3: "Medium", 2: "Low", 1: "Info"}
    return labels.get(severity, "Unknown")


def _status_description(status_code: int) -> str:
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


def _percent_change(old: float | int, new: float | int) -> float:
    """Calculate percentage change between two values."""
    if old == 0:
        return 100.0 if new > 0 else 0.0
    return ((new - old) / old) * 100


def _generate_audit_recommendations(
    severity_counts: dict[str, int],
    top_issues: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Generate recommendations based on audit issues."""
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

    return recommendations[:5]


def _generate_performance_recommendations(
    total_clicks: int,
    avg_ctr: float,
    avg_position: float,
    trends: dict[str, float],
    top_queries: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Generate recommendations based on performance data."""
    recommendations = []

    if avg_ctr < 2:
        recommendations.append({
            "title": "Improve Click-Through Rate",
            "description": (
                f"Your average CTR of {avg_ctr:.2f}% is below optimal. "
                "Consider improving title tags and meta descriptions to increase clicks."
            ),
        })

    if avg_position > 20:
        recommendations.append({
            "title": "Focus on Ranking Improvement",
            "description": (
                f"Your average position of {avg_position:.1f} indicates room for improvement. "
                "Focus on content quality and backlink building."
            ),
        })

    if trends["clicks_change"] < -10:
        recommendations.append({
            "title": "Investigate Traffic Decline",
            "description": (
                f"Traffic has declined by {abs(trends['clicks_change']):.1f}% compared to "
                "the previous period. Review recent algorithm updates and content changes."
            ),
        })

    if trends["position_change"] > 5:
        recommendations.append({
            "title": "Address Ranking Drop",
            "description": (
                "Average position has worsened. Check for technical issues, "
                "competitor activity, or content freshness problems."
            ),
        })

    return recommendations[:5]


def _calculate_health_score(
    audit_ctx: dict[str, Any],
    backlinks_ctx: dict[str, Any],
    performance_ctx: dict[str, Any],
) -> float:
    """Calculate overall site health score (0-100)."""
    score = 100.0

    # Deduct for issues
    issues = audit_ctx["issues_summary"]
    score -= issues["critical"] * 5
    score -= issues["high"] * 2
    score -= issues["medium"] * 0.5
    score -= issues["low"] * 0.1

    # Add points for backlinks
    backlinks = backlinks_ctx["summary"]["total_backlinks"]
    domains = backlinks_ctx["summary"]["referring_domains"]
    if domains > 100:
        score += 10
    elif domains > 50:
        score += 5
    elif domains > 10:
        score += 2

    # Add points for performance
    if performance_ctx["summary"]["avg_position"] < 10:
        score += 10
    elif performance_ctx["summary"]["avg_position"] < 20:
        score += 5

    if performance_ctx["summary"]["avg_ctr"] > 5:
        score += 5
    elif performance_ctx["summary"]["avg_ctr"] > 3:
        score += 2

    return max(0, min(100, score))


def _generate_overview_recommendations(
    audit_ctx: dict[str, Any],
    backlinks_ctx: dict[str, Any],
    performance_ctx: dict[str, Any],
) -> list[dict[str, str]]:
    """Generate combined recommendations for overview report."""
    recommendations = []

    # Prioritize critical issues
    critical = audit_ctx["issues_summary"]["critical"]
    if critical > 0:
        recommendations.append({
            "title": "Fix Critical SEO Issues",
            "description": f"Address {critical} critical issues immediately to prevent ranking drops.",
            "priority": "Critical",
            "priority_level": 5,
        })

    # Backlink opportunities
    domains = backlinks_ctx["summary"]["referring_domains"]
    if domains < 50:
        recommendations.append({
            "title": "Build More Backlinks",
            "description": "Your referring domain count is low. Focus on content marketing and outreach.",
            "priority": "High",
            "priority_level": 4,
        })

    # Performance improvements
    if performance_ctx["summary"]["avg_ctr"] < 2:
        recommendations.append({
            "title": "Optimize Titles and Descriptions",
            "description": "Low CTR suggests your search snippets need improvement.",
            "priority": "Medium",
            "priority_level": 3,
        })

    return recommendations[:5]


def _generate_action_items(
    audit_ctx: dict[str, Any],
    backlinks_ctx: dict[str, Any],
    performance_ctx: dict[str, Any],
) -> list[dict[str, str]]:
    """Generate prioritized action items for overview report."""
    items = []

    # Critical issues
    if audit_ctx["issues_summary"]["critical"] > 0:
        items.append({
            "priority": "Critical",
            "priority_level": 5,
            "action": f"Fix {audit_ctx['issues_summary']['critical']} critical issues",
            "impact": "Prevent ranking penalties and improve user experience",
        })

    # High issues
    if audit_ctx["issues_summary"]["high"] > 10:
        items.append({
            "priority": "High",
            "priority_level": 4,
            "action": f"Address {audit_ctx['issues_summary']['high']} high-priority issues",
            "impact": "Improve search rankings and site performance",
        })

    # Backlink building
    if backlinks_ctx["summary"]["referring_domains"] < 100:
        items.append({
            "priority": "Medium",
            "priority_level": 3,
            "action": "Increase referring domain count",
            "impact": "Boost domain authority and organic visibility",
        })

    # CTR improvement
    if performance_ctx["summary"]["avg_ctr"] < 3:
        items.append({
            "priority": "Medium",
            "priority_level": 3,
            "action": "Optimize meta titles and descriptions",
            "impact": "Increase click-through rate from search results",
        })

    return items[:5]
