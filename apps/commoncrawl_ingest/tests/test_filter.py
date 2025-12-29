"""
TDD tests for the domain filtering module.

Tests cover:
- DomainFilter with target domains
- Wildcard domain patterns
- Sample rate filtering
- Edge cases and error handling
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


# ============================================================================
# Tests for DomainFilter initialization
# ============================================================================


class TestDomainFilterInit:
    """Tests for DomainFilter initialization."""

    def test_domain_filter_accepts_target_domains(self) -> None:
        """DomainFilter should accept a list of target domains."""
        from semrush_commoncrawl.filter import DomainFilter

        filter = DomainFilter(target_domains=["example.com", "test.org"])

        assert filter.target_domains == ["example.com", "test.org"]

    def test_domain_filter_accepts_none_target_domains(self) -> None:
        """DomainFilter should accept None for target_domains (no filtering)."""
        from semrush_commoncrawl.filter import DomainFilter

        filter = DomainFilter(target_domains=None)

        assert filter.target_domains is None

    def test_domain_filter_accepts_sample_rate(self) -> None:
        """DomainFilter should accept sample_rate between 0 and 1."""
        from semrush_commoncrawl.filter import DomainFilter

        filter = DomainFilter(sample_rate=0.5)

        assert filter.sample_rate == 0.5

    def test_domain_filter_default_sample_rate_is_one(self) -> None:
        """DomainFilter should default sample_rate to 1.0 (no sampling)."""
        from semrush_commoncrawl.filter import DomainFilter

        filter = DomainFilter()

        assert filter.sample_rate == 1.0

    def test_domain_filter_validates_sample_rate_range(self) -> None:
        """DomainFilter should validate sample_rate is between 0 and 1."""
        from semrush_commoncrawl.filter import DomainFilter

        with pytest.raises(ValueError, match="sample_rate must be between 0 and 1"):
            DomainFilter(sample_rate=1.5)

        with pytest.raises(ValueError, match="sample_rate must be between 0 and 1"):
            DomainFilter(sample_rate=-0.1)


# ============================================================================
# Tests for DomainFilter.should_include with exact domains
# ============================================================================


class TestDomainFilterExactMatch:
    """Tests for exact domain matching."""

    def test_should_include_matches_exact_domain(self) -> None:
        """should_include should return True for exact domain match."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["example.com"])
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://example.com/page",
            target_domain="example.com",
        )

        assert filter.should_include(edge) is True

    def test_should_include_rejects_non_matching_domain(self) -> None:
        """should_include should return False for non-matching domain."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["example.com"])
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://other.com/page",
            target_domain="other.com",
        )

        assert filter.should_include(edge) is False

    def test_should_include_matches_any_target_domain(self) -> None:
        """should_include should return True if any target domain matches."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["example.com", "test.org", "demo.net"])
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://test.org/page",
            target_domain="test.org",
        )

        assert filter.should_include(edge) is True

    def test_should_include_is_case_insensitive(self) -> None:
        """should_include should match domains case-insensitively."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["Example.COM"])
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://example.com/page",
            target_domain="example.com",
        )

        assert filter.should_include(edge) is True

    def test_should_include_all_when_no_target_domains(self) -> None:
        """should_include should return True for all edges when target_domains is None."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=None)
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://any-domain.com/page",
            target_domain="any-domain.com",
        )

        assert filter.should_include(edge) is True


# ============================================================================
# Tests for DomainFilter.should_include with wildcards
# ============================================================================


class TestDomainFilterWildcard:
    """Tests for wildcard domain patterns."""

    def test_wildcard_matches_subdomain(self) -> None:
        """Wildcard *.example.com should match subdomains."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["*.example.com"])
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://blog.example.com/page",
            target_domain="example.com",  # Registered domain
        )

        # For wildcard, we match on target_url containing the pattern
        assert filter.should_include(edge) is True

    def test_wildcard_matches_www_subdomain(self) -> None:
        """Wildcard *.example.com should match www.example.com."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["*.example.com"])
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://www.example.com/page",
            target_domain="example.com",
        )

        assert filter.should_include(edge) is True

    def test_wildcard_does_not_match_different_domain(self) -> None:
        """Wildcard *.example.com should not match other-example.com."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["*.example.com"])
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://other-example.com/page",
            target_domain="other-example.com",
        )

        assert filter.should_include(edge) is False

    def test_wildcard_matches_deeply_nested_subdomain(self) -> None:
        """Wildcard *.example.com should match deep.nested.example.com."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["*.example.com"])
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://deep.nested.subdomain.example.com/page",
            target_domain="example.com",
        )

        assert filter.should_include(edge) is True

    def test_mixed_exact_and_wildcard_patterns(self) -> None:
        """Should support mixed exact and wildcard patterns."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["exact.com", "*.wildcard.org"])

        edge1 = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://exact.com/page",
            target_domain="exact.com",
        )

        edge2 = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://sub.wildcard.org/page",
            target_domain="wildcard.org",
        )

        edge3 = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://other.com/page",
            target_domain="other.com",
        )

        assert filter.should_include(edge1) is True
        assert filter.should_include(edge2) is True
        assert filter.should_include(edge3) is False


# ============================================================================
# Tests for DomainFilter.should_include with sample rate
# ============================================================================


class TestDomainFilterSampleRate:
    """Tests for sample rate filtering."""

    def test_sample_rate_one_includes_all(self) -> None:
        """Sample rate 1.0 should include all edges."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(sample_rate=1.0)

        included_count = 0
        for i in range(100):
            edge = Edge(
                source_url=f"https://source{i}.com/page",
                source_domain=f"source{i}.com",
                target_url=f"https://target{i}.com/page",
                target_domain=f"target{i}.com",
            )
            if filter.should_include(edge):
                included_count += 1

        assert included_count == 100

    def test_sample_rate_zero_includes_none(self) -> None:
        """Sample rate 0.0 should include no edges."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(sample_rate=0.0)

        included_count = 0
        for i in range(100):
            edge = Edge(
                source_url=f"https://source{i}.com/page",
                source_domain=f"source{i}.com",
                target_url=f"https://target{i}.com/page",
                target_domain=f"target{i}.com",
            )
            if filter.should_include(edge):
                included_count += 1

        assert included_count == 0

    def test_sample_rate_half_includes_approximately_half(self) -> None:
        """Sample rate 0.5 should include approximately 50% of edges."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        # Use fixed seed for reproducibility
        random.seed(42)

        filter = DomainFilter(sample_rate=0.5)

        included_count = 0
        total = 1000
        for i in range(total):
            edge = Edge(
                source_url=f"https://source{i}.com/page",
                source_domain=f"source{i}.com",
                target_url=f"https://target{i}.com/page",
                target_domain=f"target{i}.com",
            )
            if filter.should_include(edge):
                included_count += 1

        # Allow 10% tolerance
        assert 400 <= included_count <= 600

    def test_sample_rate_combined_with_domain_filter(self) -> None:
        """Sample rate should work together with domain filtering."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        random.seed(42)

        filter = DomainFilter(target_domains=["target.com"], sample_rate=0.5)

        # Create edges - half targeting target.com, half targeting other.com
        included_count = 0
        matching_domain_count = 0

        for i in range(1000):
            domain = "target.com" if i % 2 == 0 else "other.com"
            edge = Edge(
                source_url=f"https://source{i}.com/page",
                source_domain=f"source{i}.com",
                target_url=f"https://{domain}/page",
                target_domain=domain,
            )
            if domain == "target.com":
                matching_domain_count += 1
            if filter.should_include(edge):
                included_count += 1

        # Should be approximately half of the matching domain edges
        # 500 match domain, ~250 should pass sample rate
        assert 175 <= included_count <= 325


# ============================================================================
# Tests for edge cases
# ============================================================================


class TestDomainFilterEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_target_domains_list(self) -> None:
        """Empty target_domains list should include no edges."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=[])
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://target.com/page",
            target_domain="target.com",
        )

        # Empty list means no domains match
        assert filter.should_include(edge) is False

    def test_handles_edge_with_empty_target_domain(self) -> None:
        """Should handle edge with empty target domain gracefully."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["example.com"])
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="",
            target_domain="",
        )

        assert filter.should_include(edge) is False

    def test_handles_whitespace_in_domain(self) -> None:
        """Should handle whitespace in domain names."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["  example.com  "])
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://example.com/page",
            target_domain="example.com",
        )

        # Should strip whitespace and match
        assert filter.should_include(edge) is True

    def test_handles_punycode_domains(self) -> None:
        """Should handle punycode (internationalized) domains."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["xn--n3h.com"])  # Punycode for emoji domain
        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://xn--n3h.com/page",
            target_domain="xn--n3h.com",
        )

        assert filter.should_include(edge) is True


# ============================================================================
# Tests for filter statistics
# ============================================================================


class TestDomainFilterStats:
    """Tests for filter statistics tracking."""

    def test_filter_tracks_total_processed(self) -> None:
        """Filter should track total edges processed."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["example.com"])

        for i in range(10):
            edge = Edge(
                source_url=f"https://source{i}.com/page",
                source_domain=f"source{i}.com",
                target_url=f"https://target{i}.com/page",
                target_domain=f"target{i}.com",
            )
            filter.should_include(edge)

        assert filter.stats.total_processed == 10

    def test_filter_tracks_total_included(self) -> None:
        """Filter should track total edges included."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["target.com"])

        for i in range(10):
            domain = "target.com" if i % 2 == 0 else "other.com"
            edge = Edge(
                source_url=f"https://source{i}.com/page",
                source_domain=f"source{i}.com",
                target_url=f"https://{domain}/page",
                target_domain=domain,
            )
            filter.should_include(edge)

        assert filter.stats.total_included == 5

    def test_filter_tracks_total_excluded(self) -> None:
        """Filter should track total edges excluded."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["target.com"])

        for i in range(10):
            domain = "target.com" if i % 2 == 0 else "other.com"
            edge = Edge(
                source_url=f"https://source{i}.com/page",
                source_domain=f"source{i}.com",
                target_url=f"https://{domain}/page",
                target_domain=domain,
            )
            filter.should_include(edge)

        assert filter.stats.total_excluded == 5

    def test_filter_reset_stats(self) -> None:
        """Filter should support resetting stats."""
        from semrush_commoncrawl.filter import DomainFilter
        from semrush_commoncrawl.parser import Edge

        filter = DomainFilter(target_domains=["target.com"])

        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://target.com/page",
            target_domain="target.com",
        )
        filter.should_include(edge)

        assert filter.stats.total_processed == 1

        filter.reset_stats()

        assert filter.stats.total_processed == 0
        assert filter.stats.total_included == 0
        assert filter.stats.total_excluded == 0
