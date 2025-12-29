"""
Domain filtering for Common Crawl ingestion.

Provides configurable filtering of link edges based on target domains,
wildcard patterns, and sample rate for controlled ingestion.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from semrush_commoncrawl.parser import Edge


@dataclass
class FilterStats:
    """
    Statistics for filter operations.

    Tracks the number of edges processed, included, and excluded
    during filtering.

    Attributes:
        total_processed: Total edges passed through the filter.
        total_included: Edges that passed the filter.
        total_excluded: Edges that were filtered out.
    """

    total_processed: int = 0
    total_included: int = 0
    total_excluded: int = 0

    def reset(self) -> None:
        """Reset all statistics to zero."""
        self.total_processed = 0
        self.total_included = 0
        self.total_excluded = 0


@dataclass
class DomainFilter:
    """
    Filter for link edges based on target domain.

    Supports exact domain matching, wildcard patterns (*.example.com),
    and random sampling for controlled ingestion volume.

    Attributes:
        target_domains: List of target domains to filter for.
            If None, all domains are accepted (no filtering).
            Supports wildcard patterns like "*.example.com".
        sample_rate: Random sampling rate between 0.0 and 1.0.
            1.0 means include all matching edges.
            0.5 means include approximately half of matching edges.

    Examples:
        >>> filter = DomainFilter(target_domains=["example.com"])
        >>> filter.should_include(edge_to_example)
        True

        >>> filter = DomainFilter(target_domains=["*.example.com"])
        >>> filter.should_include(edge_to_subdomain_example)
        True
    """

    target_domains: list[str] | None = None
    sample_rate: float = 1.0
    stats: FilterStats = field(default_factory=FilterStats)

    # Internal: compiled patterns for wildcard matching
    _patterns: list[tuple[str, bool, re.Pattern[str] | None]] = field(
        default_factory=list, init=False, repr=False
    )

    def __post_init__(self) -> None:
        """Validate and compile domain patterns."""
        # Validate sample_rate
        if not 0.0 <= self.sample_rate <= 1.0:
            raise ValueError("sample_rate must be between 0 and 1")

        # Compile patterns
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile domain patterns for efficient matching."""
        self._patterns = []

        if self.target_domains is None:
            return

        for domain in self.target_domains:
            domain = domain.strip().lower()
            if not domain:
                continue

            if domain.startswith("*."):
                # Wildcard pattern - matches subdomains
                # *.example.com matches sub.example.com, www.example.com, etc.
                base_domain = domain[2:]  # Remove *.
                # Create regex pattern that matches the domain in a URL
                pattern = re.compile(rf"(?:^|\.){re.escape(base_domain)}$", re.IGNORECASE)
                self._patterns.append((domain, True, pattern))
            else:
                # Exact domain match
                self._patterns.append((domain, False, None))

    def should_include(self, edge: Edge) -> bool:
        """
        Check if an edge should be included based on filter criteria.

        Applies domain filtering first, then random sampling.

        Args:
            edge: The Edge to check.

        Returns:
            True if the edge passes all filters, False otherwise.
        """
        self.stats.total_processed += 1

        # Check domain filter
        if not self._matches_domain_filter(edge):
            self.stats.total_excluded += 1
            return False

        # Check sample rate
        if not self._passes_sample_rate():
            self.stats.total_excluded += 1
            return False

        self.stats.total_included += 1
        return True

    def _matches_domain_filter(self, edge: Edge) -> bool:
        """Check if edge matches domain filter criteria."""
        # No filter means include all
        if self.target_domains is None:
            return True

        # Empty list means include none
        if not self._patterns:
            return False

        target_domain = edge.target_domain.lower()
        target_url = edge.target_url.lower()

        if not target_domain:
            return False

        for original_pattern, is_wildcard, regex in self._patterns:
            if is_wildcard:
                # For wildcard patterns, we need to check the full hostname
                # Extract hostname from target_url
                try:
                    parsed = urlparse(target_url)
                    hostname = parsed.netloc.lower()
                except Exception:
                    hostname = ""

                if regex and regex.search(hostname):
                    return True
            else:
                # Exact domain match
                if target_domain == original_pattern:
                    return True

        return False

    def _passes_sample_rate(self) -> bool:
        """Check if this edge passes random sampling."""
        if self.sample_rate >= 1.0:
            return True
        if self.sample_rate <= 0.0:
            return False

        return random.random() < self.sample_rate

    def reset_stats(self) -> None:
        """Reset filter statistics."""
        self.stats.reset()
