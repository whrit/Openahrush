"""
Tests for URL frontier manager.

TDD tests covering:
- URL normalization for deduplication
- Priority queue ordering by depth
- Max depth and max pages limits
- Deduplication via seen set
"""

from __future__ import annotations

from semrush_workers.crawl.frontier import Frontier, FrontierSettings


class TestFrontierSettings:
    """Tests for FrontierSettings configuration."""

    def test_default_settings(self) -> None:
        """Default settings should have sensible values."""
        settings = FrontierSettings()
        assert settings.max_depth == 10
        assert settings.max_pages == 500

    def test_custom_settings(self) -> None:
        """Custom settings should override defaults."""
        settings = FrontierSettings(max_depth=5, max_pages=100)
        assert settings.max_depth == 5
        assert settings.max_pages == 100


class TestFrontierBasics:
    """Basic frontier operations."""

    def test_create_frontier_with_seed_url(self) -> None:
        """Frontier should accept a seed URL on creation."""
        frontier = Frontier(seed_url="https://example.com")
        assert frontier.size() == 1

    def test_create_frontier_with_settings(self) -> None:
        """Frontier should accept custom settings."""
        settings = FrontierSettings(max_depth=3, max_pages=50)
        frontier = Frontier(seed_url="https://example.com", settings=settings)
        assert frontier.settings.max_depth == 3
        assert frontier.settings.max_pages == 50

    def test_pop_returns_url_with_depth(self) -> None:
        """Pop should return (depth, url) tuple."""
        frontier = Frontier(seed_url="https://example.com")
        result = frontier.pop()
        assert result is not None
        depth, url = result
        assert depth == 0
        assert "example.com" in url

    def test_pop_empty_frontier_returns_none(self) -> None:
        """Pop on empty frontier should return None."""
        frontier = Frontier(seed_url="https://example.com")
        frontier.pop()  # Remove the seed
        result = frontier.pop()
        assert result is None

    def test_size_tracks_queue_length(self) -> None:
        """Size should reflect current queue length."""
        frontier = Frontier(seed_url="https://example.com")
        assert frontier.size() == 1
        frontier.pop()
        assert frontier.size() == 0


class TestFrontierAdd:
    """Tests for adding URLs to frontier."""

    def test_add_new_url_returns_true(self) -> None:
        """Adding a new URL should return True."""
        frontier = Frontier(seed_url="https://example.com")
        result = frontier.add("https://example.com/page1", depth=1)
        assert result is True

    def test_add_duplicate_url_returns_false(self) -> None:
        """Adding a duplicate URL should return False."""
        frontier = Frontier(seed_url="https://example.com")
        frontier.add("https://example.com/page1", depth=1)
        result = frontier.add("https://example.com/page1", depth=1)
        assert result is False

    def test_add_url_exceeding_max_depth_returns_false(self) -> None:
        """URL exceeding max_depth should not be added."""
        settings = FrontierSettings(max_depth=2)
        frontier = Frontier(seed_url="https://example.com", settings=settings)
        result = frontier.add("https://example.com/deep", depth=3)
        assert result is False
        # Queue should only have seed URL
        assert frontier.size() == 1

    def test_add_url_at_max_depth_returns_true(self) -> None:
        """URL at exactly max_depth should be added."""
        settings = FrontierSettings(max_depth=2)
        frontier = Frontier(seed_url="https://example.com", settings=settings)
        result = frontier.add("https://example.com/page", depth=2)
        assert result is True


class TestFrontierMaxPages:
    """Tests for max_pages limit."""

    def test_max_pages_limits_total_urls(self) -> None:
        """Frontier should stop accepting URLs after max_pages."""
        settings = FrontierSettings(max_pages=3)
        frontier = Frontier(seed_url="https://example.com", settings=settings)
        # Seed counts as 1
        assert frontier.add("https://example.com/page1", depth=1) is True  # 2
        assert frontier.add("https://example.com/page2", depth=1) is True  # 3
        assert frontier.add("https://example.com/page3", depth=1) is False  # exceeds

    def test_is_at_capacity_returns_true_when_full(self) -> None:
        """is_at_capacity should return True when max_pages reached."""
        settings = FrontierSettings(max_pages=2)
        frontier = Frontier(seed_url="https://example.com", settings=settings)
        frontier.add("https://example.com/page1", depth=1)
        assert frontier.is_at_capacity() is True

    def test_total_seen_counts_all_urls(self) -> None:
        """total_seen should count all URLs ever added."""
        settings = FrontierSettings(max_pages=10)
        frontier = Frontier(seed_url="https://example.com", settings=settings)
        frontier.add("https://example.com/page1", depth=1)
        frontier.add("https://example.com/page2", depth=1)
        assert frontier.total_seen() == 3  # seed + 2 pages


class TestFrontierNormalization:
    """Tests for URL normalization and deduplication."""

    def test_trailing_slash_normalized(self) -> None:
        """URLs with/without trailing slash should be treated as same."""
        frontier = Frontier(seed_url="https://example.com/page")
        result = frontier.add("https://example.com/page/", depth=1)
        assert result is False  # Should be seen as duplicate

    def test_case_insensitive_path(self) -> None:
        """URL paths should be case-insensitive for deduplication."""
        frontier = Frontier(seed_url="https://example.com/Page")
        result = frontier.add("https://example.com/page", depth=1)
        assert result is False  # Should be seen as duplicate

    def test_query_params_sorted(self) -> None:
        """Query params should be sorted for consistent comparison."""
        frontier = Frontier(seed_url="https://example.com/page?b=2&a=1")
        result = frontier.add("https://example.com/page?a=1&b=2", depth=1)
        assert result is False  # Should be seen as duplicate

    def test_tracking_params_removed(self) -> None:
        """Tracking parameters like utm_source should be stripped."""
        frontier = Frontier(seed_url="https://example.com/page")
        result = frontier.add("https://example.com/page?utm_source=google", depth=1)
        assert result is False  # Should be seen as duplicate

    def test_different_fragments_same_url(self) -> None:
        """URLs differing only by fragment should be duplicates."""
        frontier = Frontier(seed_url="https://example.com/page")
        result = frontier.add("https://example.com/page#section", depth=1)
        assert result is False  # Should be seen as duplicate


class TestFrontierPriorityOrdering:
    """Tests for depth-based priority ordering."""

    def test_lower_depth_popped_first(self) -> None:
        """URLs with lower depth should be popped first (BFS)."""
        frontier = Frontier(seed_url="https://example.com")
        frontier.add("https://example.com/deep", depth=3)
        frontier.add("https://example.com/shallow", depth=1)
        frontier.add("https://example.com/medium", depth=2)

        # Seed URL at depth 0 should come first
        depth, url = frontier.pop()  # type: ignore
        assert depth == 0

        # Then depth 1
        depth, url = frontier.pop()  # type: ignore
        assert depth == 1
        assert "shallow" in url

        # Then depth 2
        depth, url = frontier.pop()  # type: ignore
        assert depth == 2

        # Then depth 3
        depth, url = frontier.pop()  # type: ignore
        assert depth == 3

    def test_fifo_within_same_depth(self) -> None:
        """URLs at same depth should be FIFO ordered."""
        frontier = Frontier(seed_url="https://example.com")
        frontier.pop()  # Remove seed
        frontier.add("https://example.com/first", depth=1)
        frontier.add("https://example.com/second", depth=1)
        frontier.add("https://example.com/third", depth=1)

        _, url1 = frontier.pop()  # type: ignore
        _, url2 = frontier.pop()  # type: ignore
        _, url3 = frontier.pop()  # type: ignore

        assert "first" in url1
        assert "second" in url2
        assert "third" in url3


class TestFrontierEdgeCases:
    """Tests for edge cases."""

    def test_empty_url_rejected(self) -> None:
        """Empty URLs should be rejected."""
        frontier = Frontier(seed_url="https://example.com")
        result = frontier.add("", depth=1)
        assert result is False

    def test_invalid_url_rejected(self) -> None:
        """Invalid URLs should be rejected."""
        frontier = Frontier(seed_url="https://example.com")
        result = frontier.add("not-a-url", depth=1)
        assert result is False

    def test_javascript_url_rejected(self) -> None:
        """javascript: URLs should be rejected."""
        frontier = Frontier(seed_url="https://example.com")
        result = frontier.add("javascript:void(0)", depth=1)
        assert result is False

    def test_mailto_url_rejected(self) -> None:
        """mailto: URLs should be rejected."""
        frontier = Frontier(seed_url="https://example.com")
        result = frontier.add("mailto:test@example.com", depth=1)
        assert result is False

    def test_tel_url_rejected(self) -> None:
        """tel: URLs should be rejected."""
        frontier = Frontier(seed_url="https://example.com")
        result = frontier.add("tel:+1234567890", depth=1)
        assert result is False

    def test_data_url_rejected(self) -> None:
        """data: URLs should be rejected."""
        frontier = Frontier(seed_url="https://example.com")
        result = frontier.add("data:text/html,<h1>Test</h1>", depth=1)
        assert result is False

    def test_unicode_url_handled(self) -> None:
        """Unicode URLs should be properly handled."""
        frontier = Frontier(seed_url="https://example.com")
        # URL with unicode characters
        result = frontier.add("https://example.com/cafe", depth=1)
        assert result is True

    def test_url_with_port(self) -> None:
        """URLs with non-standard ports should be preserved."""
        frontier = Frontier(seed_url="https://example.com:8080")
        result = frontier.add("https://example.com:8080/page", depth=1)
        assert result is True

    def test_default_ports_removed(self) -> None:
        """Default ports (80, 443) should be removed during normalization."""
        frontier = Frontier(seed_url="https://example.com:443/page")
        result = frontier.add("https://example.com/page", depth=1)
        assert result is False  # Should be duplicate


class TestFrontierReset:
    """Tests for frontier reset functionality."""

    def test_reset_clears_queue(self) -> None:
        """Reset should clear the queue."""
        frontier = Frontier(seed_url="https://example.com")
        frontier.add("https://example.com/page1", depth=1)
        frontier.reset()
        assert frontier.size() == 0

    def test_reset_clears_seen_set(self) -> None:
        """Reset should clear the seen set."""
        frontier = Frontier(seed_url="https://example.com")
        frontier.reset()
        # Should be able to add the seed URL again
        result = frontier.add("https://example.com", depth=0)
        assert result is True
