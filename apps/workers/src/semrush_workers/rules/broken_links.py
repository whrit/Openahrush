"""
Broken link detection for site audits.

This module provides utilities for detecting broken internal links:
- Queries link_edges where is_internal=true
- Joins with crawl_pages to get target status
- Creates issues for 4xx/5xx targets
- Counts unique broken URLs, not duplicate edges
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from semrush_workers.rules.models import IssueInstance, IssueSeverity, LinkEdge

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class BrokenLinkSummary:
    """
    Summary of broken link analysis.

    Attributes:
        total_internal_links: Total number of internal links checked.
        broken_link_count: Number of unique broken link targets.
        broken_by_status: Count of broken links by status code.
        issues_created: Number of issue instances created.
    """

    total_internal_links: int = 0
    broken_link_count: int = 0
    broken_by_status: dict[int, int] | None = None
    issues_created: int = 0

    def __post_init__(self) -> None:
        if self.broken_by_status is None:
            self.broken_by_status = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_internal_links": self.total_internal_links,
            "broken_link_count": self.broken_link_count,
            "broken_by_status": self.broken_by_status,
            "issues_created": self.issues_created,
        }


def detect_broken_links(
    edges: list[LinkEdge],
    crawl_run_id: uuid.UUID,
) -> tuple[list[IssueInstance], BrokenLinkSummary]:
    """
    Detect broken internal links from a list of link edges.

    Broken links are internal links where the target returns
    a 4xx or 5xx status code. Only unique broken targets are
    reported (not duplicate edges to the same broken URL).

    Args:
        edges: List of link edges from the crawl.
        crawl_run_id: ID of the crawl run.

    Returns:
        Tuple of (list of issues, summary).
    """
    issues: list[IssueInstance] = []
    summary = BrokenLinkSummary()

    # Track unique broken targets to avoid duplicates
    seen_targets: set[str] = set()
    broken_by_status: dict[int, int] = {}

    for edge in edges:
        if not edge.is_internal:
            continue

        summary.total_internal_links += 1

        if edge.target_status_code is None:
            continue

        if edge.target_status_code >= 400:
            # Count by status
            status = edge.target_status_code
            broken_by_status[status] = broken_by_status.get(status, 0) + 1

            # Only create issue for unique targets
            target_normalized = edge.target_url.lower().rstrip("/")
            if target_normalized not in seen_targets:
                seen_targets.add(target_normalized)
                issue = IssueInstance(
                    id=uuid.uuid4(),
                    crawl_run_id=crawl_run_id,
                    crawl_page_id=None,  # Link-level issue
                    issue_type_id="broken_internal_link",
                    affected_url=edge.target_url,
                    severity=IssueSeverity.CRITICAL,
                    confidence=1.0,
                    evidence={
                        "source_url": edge.source_url,
                        "target_url": edge.target_url,
                        "status_code": edge.target_status_code,
                        "anchor_text": edge.anchor_text,
                    },
                    created_at=datetime.now(UTC),
                )
                issues.append(issue)

    summary.broken_link_count = len(seen_targets)
    summary.broken_by_status = broken_by_status
    summary.issues_created = len(issues)

    return issues, summary


def get_broken_link_sources(
    edges: list[LinkEdge],
    target_url: str,
) -> list[dict[str, Any]]:
    """
    Get all pages that link to a broken target URL.

    Useful for showing which pages need to be fixed.

    Args:
        edges: List of link edges from the crawl.
        target_url: The broken target URL.

    Returns:
        List of source information dictionaries.
    """
    target_normalized = target_url.lower().rstrip("/")
    sources: list[dict[str, Any]] = []

    for edge in edges:
        if not edge.is_internal:
            continue
        if edge.target_url.lower().rstrip("/") == target_normalized:
            sources.append({
                "source_url": edge.source_url,
                "anchor_text": edge.anchor_text,
                "is_follow": edge.is_follow,
            })

    return sources


async def load_broken_links_from_db(
    db_session: AsyncSession,
    crawl_run_id: uuid.UUID,
) -> tuple[list[IssueInstance], BrokenLinkSummary]:
    """
    Load link edges from database and detect broken links.

    This is the database-aware version that queries the link_edges
    table for the given crawl run.

    Args:
        db_session: Async database session.
        crawl_run_id: ID of the crawl run.

    Returns:
        Tuple of (list of issues, summary).

    Note:
        This requires the link_edges table to exist with columns:
        - crawl_run_id, source_url, target_url, is_internal, target_status_code
    """
    from sqlalchemy import text

    # Query internal links with their target status codes
    # This assumes a link_edges table exists (to be created in migration)
    query = text("""
        SELECT
            id,
            crawl_run_id,
            source_url,
            target_url,
            anchor_text,
            is_internal,
            is_follow,
            target_status_code
        FROM link_edges
        WHERE crawl_run_id = :crawl_run_id
          AND is_internal = true
    """)

    result = await db_session.execute(query, {"crawl_run_id": crawl_run_id})
    rows = result.fetchall()

    # Convert to LinkEdge objects
    edges: list[LinkEdge] = []
    for row in rows:
        edge = LinkEdge(
            id=row.id,
            crawl_run_id=row.crawl_run_id,
            source_url=row.source_url,
            target_url=row.target_url,
            anchor_text=row.anchor_text,
            is_internal=row.is_internal,
            is_follow=row.is_follow if hasattr(row, "is_follow") else True,
            target_status_code=row.target_status_code,
        )
        edges.append(edge)

    return detect_broken_links(edges, crawl_run_id)
