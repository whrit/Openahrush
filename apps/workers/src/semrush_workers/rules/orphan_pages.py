"""
Orphan page detection for site audits.

This module provides utilities for detecting orphan pages:
- Queries pages discovered via sitemap
- Checks if any internal link points to them
- Creates low-severity issues for orphans

Orphan pages are pages that:
1. Were discovered via sitemap (not by following links)
2. Have no internal links pointing to them

These pages may not be properly indexed by search engines
and are harder for users to discover.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from semrush_workers.rules.models import (
    CrawlPage,
    DiscoverySource,
    IssueInstance,
    IssueSeverity,
    LinkEdge,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class OrphanPageSummary:
    """
    Summary of orphan page analysis.

    Attributes:
        total_sitemap_pages: Pages discovered via sitemap.
        orphan_count: Number of orphan pages found.
        linked_count: Sitemap pages that are internally linked.
        issues_created: Number of issue instances created.
    """

    total_sitemap_pages: int = 0
    orphan_count: int = 0
    linked_count: int = 0
    issues_created: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_sitemap_pages": self.total_sitemap_pages,
            "orphan_count": self.orphan_count,
            "linked_count": self.linked_count,
            "issues_created": self.issues_created,
        }


def detect_orphan_pages(
    pages: list[CrawlPage],
    edges: list[LinkEdge],
    crawl_run_id: uuid.UUID,
) -> tuple[list[IssueInstance], OrphanPageSummary]:
    """
    Detect orphan pages from crawl data.

    An orphan page is one that:
    1. Was discovered via sitemap
    2. Has no internal links pointing to it

    Args:
        pages: List of crawl pages.
        edges: List of link edges from the crawl.
        crawl_run_id: ID of the crawl run.

    Returns:
        Tuple of (list of issues, summary).
    """
    issues: list[IssueInstance] = []
    summary = OrphanPageSummary()

    # Build set of internally linked URLs (normalized)
    linked_urls: set[str] = set()
    for edge in edges:
        if edge.is_internal:
            linked_urls.add(edge.target_url.lower().rstrip("/"))

    # Find sitemap pages not internally linked
    for page in pages:
        if page.discovery_source != DiscoverySource.SITEMAP:
            continue

        summary.total_sitemap_pages += 1
        page_normalized = page.url.lower().rstrip("/")

        if page_normalized in linked_urls:
            summary.linked_count += 1
        else:
            summary.orphan_count += 1
            issue = IssueInstance(
                id=uuid.uuid4(),
                crawl_run_id=crawl_run_id,
                crawl_page_id=page.id,
                issue_type_id="orphan_page",
                affected_url=page.url,
                severity=IssueSeverity.LOW,
                confidence=0.9,
                evidence={
                    "discovery_source": page.discovery_source.value,
                    "internal_links_to_page": 0,
                    "url": page.url,
                },
                created_at=datetime.now(UTC),
            )
            issues.append(issue)

    summary.issues_created = len(issues)
    return issues, summary


def get_internal_links_to_page(
    edges: list[LinkEdge],
    target_url: str,
) -> list[dict[str, Any]]:
    """
    Get all internal links pointing to a specific page.

    Useful for checking if a page is truly orphaned.

    Args:
        edges: List of link edges from the crawl.
        target_url: The URL to check links for.

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


def count_internal_links_per_page(
    edges: list[LinkEdge],
) -> dict[str, int]:
    """
    Count how many internal links point to each page.

    Useful for identifying pages with low internal linking.

    Args:
        edges: List of link edges from the crawl.

    Returns:
        Dictionary mapping normalized URL to link count.
    """
    counts: dict[str, int] = {}

    for edge in edges:
        if not edge.is_internal:
            continue
        target_normalized = edge.target_url.lower().rstrip("/")
        counts[target_normalized] = counts.get(target_normalized, 0) + 1

    return counts


async def load_orphan_pages_from_db(
    db_session: AsyncSession,
    crawl_run_id: uuid.UUID,
) -> tuple[list[IssueInstance], OrphanPageSummary]:
    """
    Load crawl data from database and detect orphan pages.

    This is the database-aware version that queries the crawl_pages
    and link_edges tables for the given crawl run.

    Args:
        db_session: Async database session.
        crawl_run_id: ID of the crawl run.

    Returns:
        Tuple of (list of issues, summary).

    Note:
        This requires the crawl_pages and link_edges tables to exist.
    """
    from sqlalchemy import text

    # Query sitemap pages
    pages_query = text("""
        SELECT
            id,
            crawl_run_id,
            url,
            status_code,
            title,
            meta_description,
            canonical_url,
            h1_tags,
            word_count,
            discovery_source,
            redirect_chain,
            mixed_content_urls,
            is_indexable,
            crawled_at
        FROM crawl_pages
        WHERE crawl_run_id = :crawl_run_id
          AND discovery_source = 'sitemap'
    """)

    pages_result = await db_session.execute(
        pages_query, {"crawl_run_id": crawl_run_id}
    )
    page_rows = pages_result.fetchall()

    # Query internal links
    edges_query = text("""
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

    edges_result = await db_session.execute(
        edges_query, {"crawl_run_id": crawl_run_id}
    )
    edge_rows = edges_result.fetchall()

    # Convert to model objects
    pages: list[CrawlPage] = []
    for row in page_rows:
        page = CrawlPage(
            id=row.id,
            crawl_run_id=row.crawl_run_id,
            url=row.url,
            status_code=row.status_code,
            title=row.title,
            meta_description=row.meta_description,
            canonical_url=row.canonical_url,
            h1_tags=row.h1_tags or [],
            word_count=row.word_count or 0,
            discovery_source=DiscoverySource(row.discovery_source),
            redirect_chain=row.redirect_chain or [],
            mixed_content_urls=row.mixed_content_urls or [],
            is_indexable=row.is_indexable if hasattr(row, "is_indexable") else True,
            crawled_at=row.crawled_at,
        )
        pages.append(page)

    edges: list[LinkEdge] = []
    for row in edge_rows:
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

    return detect_orphan_pages(pages, edges, crawl_run_id)
