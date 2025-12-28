"""
Tests for broken link detection.

Tests cover:
- Basic broken link detection
- Deduplication of broken targets
- Status code categorization
- Helper functions
"""

from __future__ import annotations

import uuid

from semrush_workers.rules.broken_links import (
    BrokenLinkSummary,
    detect_broken_links,
    get_broken_link_sources,
)
from semrush_workers.rules.models import LinkEdge


def make_edge(
    source_url: str = "https://example.com/page",
    target_url: str = "https://example.com/target",
    anchor_text: str | None = "Link Text",
    is_internal: bool = True,
    is_follow: bool = True,
    target_status_code: int | None = None,
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
        target_status_code=target_status_code,
    )


class TestDetectBrokenLinks:
    """Tests for detect_broken_links function."""

    def test_detects_404_links(self) -> None:
        """Should detect 404 broken links."""
        crawl_run_id = uuid.uuid4()
        edges = [
            make_edge(target_url="https://example.com/broken", target_status_code=404),
        ]

        issues, summary = detect_broken_links(edges, crawl_run_id)

        assert len(issues) == 1
        assert issues[0].issue_type_id == "broken_internal_link"
        assert issues[0].evidence["status_code"] == 404
        assert summary.broken_link_count == 1

    def test_detects_500_links(self) -> None:
        """Should detect 500 broken links."""
        crawl_run_id = uuid.uuid4()
        edges = [
            make_edge(target_url="https://example.com/error", target_status_code=500),
        ]

        issues, summary = detect_broken_links(edges, crawl_run_id)

        assert len(issues) == 1
        assert summary.broken_by_status[500] == 1

    def test_ignores_good_links(self) -> None:
        """Should not report 200 links as broken."""
        crawl_run_id = uuid.uuid4()
        edges = [
            make_edge(target_url="https://example.com/good", target_status_code=200),
        ]

        issues, summary = detect_broken_links(edges, crawl_run_id)

        assert len(issues) == 0
        assert summary.broken_link_count == 0

    def test_ignores_external_links(self) -> None:
        """Should not report external broken links."""
        crawl_run_id = uuid.uuid4()
        edges = [
            make_edge(
                target_url="https://external.com/broken",
                is_internal=False,
                target_status_code=404,
            ),
        ]

        issues, summary = detect_broken_links(edges, crawl_run_id)

        assert len(issues) == 0
        assert summary.total_internal_links == 0

    def test_deduplicates_broken_targets(self) -> None:
        """Multiple edges to same broken target should create one issue."""
        crawl_run_id = uuid.uuid4()
        edges = [
            make_edge(
                source_url="https://example.com/page1",
                target_url="https://example.com/broken",
                target_status_code=404,
            ),
            make_edge(
                source_url="https://example.com/page2",
                target_url="https://example.com/broken",
                target_status_code=404,
            ),
            make_edge(
                source_url="https://example.com/page3",
                target_url="https://example.com/broken",
                target_status_code=404,
            ),
        ]

        issues, summary = detect_broken_links(edges, crawl_run_id)

        assert len(issues) == 1
        assert summary.broken_link_count == 1
        assert summary.total_internal_links == 3

    def test_counts_by_status_code(self) -> None:
        """Should count broken links by status code."""
        crawl_run_id = uuid.uuid4()
        edges = [
            make_edge(target_url="https://example.com/404-1", target_status_code=404),
            make_edge(target_url="https://example.com/404-2", target_status_code=404),
            make_edge(target_url="https://example.com/500", target_status_code=500),
            make_edge(target_url="https://example.com/503", target_status_code=503),
        ]

        _issues, summary = detect_broken_links(edges, crawl_run_id)

        assert summary.broken_by_status[404] == 2
        assert summary.broken_by_status[500] == 1
        assert summary.broken_by_status[503] == 1

    def test_ignores_links_without_status(self) -> None:
        """Should ignore links where target wasn't crawled."""
        crawl_run_id = uuid.uuid4()
        edges = [
            make_edge(target_url="https://example.com/unknown", target_status_code=None),
        ]

        issues, summary = detect_broken_links(edges, crawl_run_id)

        assert len(issues) == 0
        assert summary.broken_link_count == 0


class TestGetBrokenLinkSources:
    """Tests for get_broken_link_sources function."""

    def test_finds_all_sources(self) -> None:
        """Should find all pages linking to broken target."""
        edges = [
            make_edge(
                source_url="https://example.com/page1",
                target_url="https://example.com/broken",
                anchor_text="Link 1",
            ),
            make_edge(
                source_url="https://example.com/page2",
                target_url="https://example.com/broken",
                anchor_text="Link 2",
            ),
            make_edge(
                source_url="https://example.com/page3",
                target_url="https://example.com/other",
                anchor_text="Other Link",
            ),
        ]

        sources = get_broken_link_sources(edges, "https://example.com/broken")

        assert len(sources) == 2
        assert sources[0]["source_url"] == "https://example.com/page1"
        assert sources[1]["source_url"] == "https://example.com/page2"

    def test_handles_trailing_slash(self) -> None:
        """Should match URLs with trailing slash differences."""
        edges = [
            make_edge(
                source_url="https://example.com/page",
                target_url="https://example.com/broken/",
            ),
        ]

        # Search without trailing slash
        sources = get_broken_link_sources(edges, "https://example.com/broken")

        # Should still find it due to normalization
        assert len(sources) == 1

    def test_ignores_external_sources(self) -> None:
        """Should not include external links."""
        edges = [
            make_edge(
                source_url="https://external.com/page",
                target_url="https://example.com/broken",
                is_internal=False,
            ),
        ]

        sources = get_broken_link_sources(edges, "https://example.com/broken")

        assert len(sources) == 0


class TestBrokenLinkSummary:
    """Tests for BrokenLinkSummary dataclass."""

    def test_to_dict(self) -> None:
        """Should serialize to dictionary."""
        summary = BrokenLinkSummary(
            total_internal_links=100,
            broken_link_count=5,
            broken_by_status={404: 3, 500: 2},
            issues_created=5,
        )

        d = summary.to_dict()

        assert d["total_internal_links"] == 100
        assert d["broken_link_count"] == 5
        assert d["broken_by_status"] == {404: 3, 500: 2}
        assert d["issues_created"] == 5

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        summary = BrokenLinkSummary()

        assert summary.total_internal_links == 0
        assert summary.broken_link_count == 0
        assert summary.broken_by_status == {}
        assert summary.issues_created == 0
