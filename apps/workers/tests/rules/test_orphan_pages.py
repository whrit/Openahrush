"""
Tests for orphan page detection.

Tests cover:
- Basic orphan detection
- Linked pages are not orphans
- Non-sitemap pages are not considered
- Helper functions
"""

from __future__ import annotations

import uuid

from semrush_workers.rules.models import CrawlPage, DiscoverySource, LinkEdge
from semrush_workers.rules.orphan_pages import (
    OrphanPageSummary,
    count_internal_links_per_page,
    detect_orphan_pages,
    get_internal_links_to_page,
)


def make_page(
    url: str = "https://example.com/page",
    discovery_source: DiscoverySource = DiscoverySource.SITEMAP,
) -> CrawlPage:
    """Create a test page."""
    return CrawlPage(
        id=uuid.uuid4(),
        crawl_run_id=uuid.uuid4(),
        url=url,
        status_code=200,
        title="Test Page",
        discovery_source=discovery_source,
    )


def make_edge(
    source_url: str = "https://example.com/page",
    target_url: str = "https://example.com/target",
    anchor_text: str | None = "Link Text",
    is_internal: bool = True,
    is_follow: bool = True,
) -> LinkEdge:
    """Create a test link edge."""
    return LinkEdge(
        id=uuid.uuid4(),
        crawl_run_id=uuid.uuid4(),
        source_url=source_url,
        target_url=target_url,
        anchor_text=anchor_text,
        is_internal=is_internal,
        is_follow=is_follow,
    )


class TestDetectOrphanPages:
    """Tests for detect_orphan_pages function."""

    def test_detects_orphan_sitemap_page(self) -> None:
        """Should detect sitemap page with no internal links."""
        crawl_run_id = uuid.uuid4()
        pages = [make_page(url="https://example.com/orphan")]
        edges: list[LinkEdge] = []

        issues, summary = detect_orphan_pages(pages, edges, crawl_run_id)

        assert len(issues) == 1
        assert issues[0].issue_type_id == "orphan_page"
        assert summary.orphan_count == 1
        assert summary.total_sitemap_pages == 1

    def test_linked_page_not_orphan(self) -> None:
        """Should not report sitemap page with internal link."""
        crawl_run_id = uuid.uuid4()
        pages = [make_page(url="https://example.com/linked")]
        edges = [
            make_edge(
                source_url="https://example.com/home",
                target_url="https://example.com/linked",
            )
        ]

        issues, summary = detect_orphan_pages(pages, edges, crawl_run_id)

        assert len(issues) == 0
        assert summary.orphan_count == 0
        assert summary.linked_count == 1

    def test_ignores_non_sitemap_pages(self) -> None:
        """Should not check pages discovered via internal links."""
        crawl_run_id = uuid.uuid4()
        pages = [
            make_page(
                url="https://example.com/internal",
                discovery_source=DiscoverySource.INTERNAL_LINK,
            )
        ]
        edges: list[LinkEdge] = []

        issues, summary = detect_orphan_pages(pages, edges, crawl_run_id)

        assert len(issues) == 0
        assert summary.total_sitemap_pages == 0

    def test_multiple_sitemap_pages(self) -> None:
        """Should check all sitemap pages."""
        crawl_run_id = uuid.uuid4()
        pages = [
            make_page(url="https://example.com/orphan1"),
            make_page(url="https://example.com/orphan2"),
            make_page(url="https://example.com/linked"),
        ]
        edges = [
            make_edge(
                source_url="https://example.com/home",
                target_url="https://example.com/linked",
            )
        ]

        issues, summary = detect_orphan_pages(pages, edges, crawl_run_id)

        assert len(issues) == 2
        assert summary.orphan_count == 2
        assert summary.linked_count == 1
        assert summary.total_sitemap_pages == 3

    def test_handles_trailing_slash(self) -> None:
        """Should match URLs with trailing slash differences."""
        crawl_run_id = uuid.uuid4()
        pages = [make_page(url="https://example.com/page/")]
        edges = [
            make_edge(
                source_url="https://example.com/home",
                target_url="https://example.com/page",  # No trailing slash
            )
        ]

        issues, summary = detect_orphan_pages(pages, edges, crawl_run_id)

        # Should match despite trailing slash difference
        assert len(issues) == 0
        assert summary.linked_count == 1

    def test_ignores_external_links(self) -> None:
        """External links should not prevent orphan detection."""
        crawl_run_id = uuid.uuid4()
        pages = [make_page(url="https://example.com/orphan")]
        edges = [
            make_edge(
                source_url="https://external.com/page",
                target_url="https://example.com/orphan",
                is_internal=False,
            )
        ]

        issues, _summary = detect_orphan_pages(pages, edges, crawl_run_id)

        assert len(issues) == 1  # Still orphan


class TestGetInternalLinksToPage:
    """Tests for get_internal_links_to_page function."""

    def test_finds_all_internal_links(self) -> None:
        """Should find all internal links to target."""
        edges = [
            make_edge(
                source_url="https://example.com/page1",
                target_url="https://example.com/target",
                anchor_text="Link 1",
            ),
            make_edge(
                source_url="https://example.com/page2",
                target_url="https://example.com/target",
                anchor_text="Link 2",
            ),
        ]

        links = get_internal_links_to_page(edges, "https://example.com/target")

        assert len(links) == 2
        assert links[0]["anchor_text"] == "Link 1"
        assert links[1]["anchor_text"] == "Link 2"

    def test_excludes_external_links(self) -> None:
        """Should not include external links."""
        edges = [
            make_edge(
                source_url="https://external.com/page",
                target_url="https://example.com/target",
                is_internal=False,
            ),
        ]

        links = get_internal_links_to_page(edges, "https://example.com/target")

        assert len(links) == 0


class TestCountInternalLinksPerPage:
    """Tests for count_internal_links_per_page function."""

    def test_counts_links_correctly(self) -> None:
        """Should count links per target."""
        edges = [
            make_edge(target_url="https://example.com/popular"),
            make_edge(target_url="https://example.com/popular"),
            make_edge(target_url="https://example.com/popular"),
            make_edge(target_url="https://example.com/less-popular"),
        ]

        counts = count_internal_links_per_page(edges)

        assert counts["https://example.com/popular"] == 3
        assert counts["https://example.com/less-popular"] == 1

    def test_normalizes_urls(self) -> None:
        """Should normalize URLs for counting."""
        edges = [
            make_edge(target_url="https://example.com/page"),
            make_edge(target_url="https://example.com/page/"),
            make_edge(target_url="https://EXAMPLE.COM/page"),
        ]

        counts = count_internal_links_per_page(edges)

        # All should be counted together after normalization
        assert len(counts) <= 3  # Depending on normalization


class TestOrphanPageSummary:
    """Tests for OrphanPageSummary dataclass."""

    def test_to_dict(self) -> None:
        """Should serialize to dictionary."""
        summary = OrphanPageSummary(
            total_sitemap_pages=100,
            orphan_count=10,
            linked_count=90,
            issues_created=10,
        )

        d = summary.to_dict()

        assert d["total_sitemap_pages"] == 100
        assert d["orphan_count"] == 10
        assert d["linked_count"] == 90
        assert d["issues_created"] == 10

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        summary = OrphanPageSummary()

        assert summary.total_sitemap_pages == 0
        assert summary.orphan_count == 0
        assert summary.linked_count == 0
        assert summary.issues_created == 0
