"""
URL frontier manager for crawl scheduling.

Provides a priority queue-based frontier with:
- Depth-based ordering (BFS crawl strategy)
- URL normalization for deduplication
- Max depth and max pages limits
- FIFO ordering within same depth level
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from urllib.parse import urlparse

from semrush_seo import normalize_url


@dataclass
class FrontierSettings:
    """
    Configuration settings for the URL frontier.

    Attributes:
        max_depth: Maximum crawl depth from seed URL (default 10).
        max_pages: Maximum total pages to crawl (default 500).
    """

    max_depth: int = 10
    max_pages: int = 500


@dataclass
class Frontier:
    """
    URL frontier manager with priority queue and deduplication.

    Uses a min-heap priority queue ordered by (depth, insertion_order)
    to implement breadth-first crawling with FIFO ordering within
    the same depth level.

    Attributes:
        seed_url: Initial URL to start crawling from.
        settings: FrontierSettings configuration.
    """

    seed_url: str
    settings: FrontierSettings = field(default_factory=FrontierSettings)

    # Internal state
    _queue: list[tuple[int, int, str]] = field(default_factory=list, init=False)
    _seen: set[str] = field(default_factory=set, init=False)
    _counter: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        """Initialize frontier with seed URL."""
        self._add_internal(self.seed_url, 0)

    def _normalize(self, url: str) -> str | None:
        """
        Normalize URL for deduplication.

        Returns None if URL is invalid or not crawlable.
        """
        if not url or not url.strip():
            return None

        url = url.strip()
        url_lower = url.lower()

        # Skip non-HTTP URLs
        if url_lower.startswith(("javascript:", "mailto:", "tel:", "data:", "#")):
            return None

        # Basic validation: URL must have a scheme or look like a valid URL
        # URLs without schemes that don't contain a dot are invalid
        if not url_lower.startswith(("http://", "https://", "//")):
            # If no scheme, must contain a dot to be valid domain
            if "." not in url:
                return None

        try:
            # Use semrush_seo normalize_url for consistent normalization
            normalized = normalize_url(
                url,
                remove_trailing_slash=True,
                lowercase_path=True,
                remove_fragments=True,
                remove_tracking_params=True,
                sort_query_params=True,
            )
            return normalized
        except ValueError:
            return None

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid for crawling."""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    def _add_internal(self, url: str, depth: int) -> bool:
        """
        Internal method to add URL to frontier.

        Returns True if URL was added, False if duplicate or invalid.
        """
        normalized = self._normalize(url)
        if normalized is None:
            return False

        if not self._is_valid_url(normalized):
            return False

        if normalized in self._seen:
            return False

        if len(self._seen) >= self.settings.max_pages:
            return False

        if depth > self.settings.max_depth:
            return False

        self._seen.add(normalized)
        # Priority tuple: (depth, insertion_order, url)
        # This ensures depth-first priority with FIFO within same depth
        heapq.heappush(self._queue, (depth, self._counter, normalized))
        self._counter += 1
        return True

    def add(self, url: str, depth: int) -> bool:
        """
        Add a URL to the frontier at the specified depth.

        Args:
            url: URL to add to the frontier.
            depth: Crawl depth of the URL.

        Returns:
            True if URL was added, False if it was a duplicate,
            exceeded max_depth, or frontier is at capacity.
        """
        return self._add_internal(url, depth)

    def pop(self) -> tuple[int, str] | None:
        """
        Get the next URL from the frontier.

        Returns:
            Tuple of (depth, url) or None if frontier is empty.
        """
        if not self._queue:
            return None

        depth, _, url = heapq.heappop(self._queue)
        return (depth, url)

    def size(self) -> int:
        """
        Get the number of URLs currently in the queue.

        Returns:
            Number of URLs waiting to be crawled.
        """
        return len(self._queue)

    def total_seen(self) -> int:
        """
        Get the total number of unique URLs seen.

        Returns:
            Total count of URLs added to frontier (including processed).
        """
        return len(self._seen)

    def is_at_capacity(self) -> bool:
        """
        Check if frontier has reached max_pages limit.

        Returns:
            True if no more URLs can be added.
        """
        return len(self._seen) >= self.settings.max_pages

    def reset(self) -> None:
        """
        Reset the frontier to empty state.

        Clears both the queue and seen set.
        """
        self._queue.clear()
        self._seen.clear()
        self._counter = 0

    def has_pending(self) -> bool:
        """
        Check if there are URLs waiting to be processed.

        Returns:
            True if queue is not empty.
        """
        return len(self._queue) > 0
