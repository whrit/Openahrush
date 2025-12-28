"""
Interfaces (protocols) for crawl components.

Defines the contracts that individual crawl components must implement.
These allow the orchestrator to work with any implementation and enable
easy mocking for testing.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from semrush_workers.crawl.models import (
        AnalysisResult,
        FetchResult,
        PageData,
        RenderedResult,
    )


class FrontierProtocol(Protocol):
    """Protocol for URL frontier management."""

    def add(self, url: str, depth: int) -> bool:
        """
        Add a URL to the frontier.

        Args:
            url: URL to add.
            depth: Crawl depth of the URL.

        Returns:
            True if URL was added, False if rejected (duplicate, depth limit, etc).
        """
        ...

    def pop(self) -> tuple[int, str] | None:
        """
        Pop the next URL to crawl.

        Returns:
            Tuple of (depth, url) or None if frontier is empty.
        """
        ...

    def size(self) -> int:
        """Return current queue size."""
        ...

    def total_seen(self) -> int:
        """Return total number of URLs ever added."""
        ...

    def is_at_capacity(self) -> bool:
        """Check if frontier has reached max_pages limit."""
        ...

    def reset(self) -> None:
        """Clear all state."""
        ...


class FetcherProtocol(Protocol):
    """Protocol for HTTP fetching."""

    async def fetch(self, url: str) -> FetchResult:
        """
        Fetch a URL and return the result.

        Args:
            url: URL to fetch.

        Returns:
            FetchResult with response data or error.
        """
        ...

    async def fetch_robots_txt(self, base_url: str) -> str | None:
        """
        Fetch robots.txt for a domain.

        Args:
            base_url: Base URL of the site.

        Returns:
            Contents of robots.txt or None if not found.
        """
        ...

    async def close(self) -> None:
        """Close any open connections."""
        ...


class ExtractorProtocol(Protocol):
    """Protocol for HTML content extraction."""

    def extract(self, html: bytes, url: str) -> PageData:
        """
        Extract SEO data from HTML content.

        Args:
            html: Raw HTML bytes.
            url: URL of the page (for resolving relative links).

        Returns:
            PageData with extracted information.
        """
        ...


class RobotsCheckerProtocol(Protocol):
    """Protocol for robots.txt checking."""

    def is_allowed(self, url: str, user_agent: str) -> bool:
        """
        Check if a URL is allowed by robots.txt.

        Args:
            url: URL to check.
            user_agent: User-Agent string.

        Returns:
            True if allowed, False if disallowed.
        """
        ...

    def get_crawl_delay(self, user_agent: str) -> float | None:
        """
        Get crawl-delay for a user agent.

        Args:
            user_agent: User-Agent string.

        Returns:
            Crawl delay in seconds or None if not specified.
        """
        ...

    def get_sitemaps(self) -> list[str]:
        """Get sitemap URLs declared in robots.txt."""
        ...


class SitemapParserProtocol(Protocol):
    """Protocol for sitemap parsing."""

    async def parse(self, sitemap_url: str) -> list[str]:
        """
        Parse a sitemap and return URLs.

        Args:
            sitemap_url: URL of the sitemap.

        Returns:
            List of URLs found in the sitemap.
        """
        ...


class RendererProtocol(Protocol):
    """Protocol for JavaScript rendering."""

    async def render(self, url: str) -> RenderedResult:
        """
        Render a page with JavaScript execution.

        Args:
            url: URL to render.

        Returns:
            RenderedResult with rendered HTML or error.
        """
        ...

    async def render_batch(self, urls: list[str]) -> list[RenderedResult]:
        """
        Render multiple pages.

        Args:
            urls: List of URLs to render.

        Returns:
            List of RenderedResults in same order as input.
        """
        ...

    async def close(self) -> None:
        """Close browser resources."""
        ...


class JSCandidateSelectorProtocol(Protocol):
    """Protocol for selecting pages that need JS rendering."""

    def select_candidates(
        self,
        pages: list[dict[str, Any]],
        budget: int,
    ) -> list[uuid.UUID]:
        """
        Select pages that should be JS-rendered.

        Args:
            pages: List of page data dictionaries.
            budget: Maximum number of pages to select.

        Returns:
            List of page IDs to render.
        """
        ...


class RulesEngineProtocol(Protocol):
    """Protocol for SEO rules engine."""

    async def analyze(
        self,
        crawl_run_id: uuid.UUID,
        pages: list[dict[str, Any]],
    ) -> AnalysisResult:
        """
        Analyze crawled pages for SEO issues.

        Args:
            crawl_run_id: ID of the crawl run.
            pages: List of page data to analyze.

        Returns:
            AnalysisResult with detected issues.
        """
        ...


class PageStorageProtocol(Protocol):
    """Protocol for crawl page storage."""

    async def store_page(
        self,
        crawl_run_id: uuid.UUID,
        url: str,
        depth: int,
        fetch_result: FetchResult,
        page_data: PageData | None,
        discovery_source: str,
    ) -> uuid.UUID:
        """
        Store a crawled page.

        Args:
            crawl_run_id: ID of the crawl run.
            url: URL of the page.
            depth: Crawl depth.
            fetch_result: HTTP fetch result.
            page_data: Extracted page data (None if not HTML).
            discovery_source: How the page was discovered.

        Returns:
            ID of the stored page record.
        """
        ...

    async def store_link_edge(
        self,
        crawl_run_id: uuid.UUID,
        source_url: str,
        target_url: str,
        anchor_text: str | None,
        is_internal: bool,
        is_follow: bool,
    ) -> uuid.UUID:
        """
        Store a link edge between pages.

        Returns:
            ID of the stored link edge record.
        """
        ...

    async def get_pages_for_analysis(
        self,
        crawl_run_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """
        Get all pages for a crawl run for analysis.

        Returns:
            List of page data dictionaries.
        """
        ...

    async def get_js_candidates(
        self,
        crawl_run_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """
        Get pages that are candidates for JS rendering.

        Returns:
            List of page data with heuristic scores.
        """
        ...

    async def update_page_with_rendered_data(
        self,
        page_id: uuid.UUID,
        page_data: PageData,
    ) -> None:
        """
        Update a page record with JS-rendered data.

        Args:
            page_id: ID of the page to update.
            page_data: New extracted data from rendered HTML.
        """
        ...


class CrawlRunStorageProtocol(Protocol):
    """Protocol for crawl run record storage."""

    async def create_crawl_run(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        seed_url: str,
        config_snapshot: dict[str, Any],
    ) -> uuid.UUID:
        """
        Create a new crawl run record.

        Returns:
            ID of the created crawl run.
        """
        ...

    async def update_status(
        self,
        crawl_run_id: uuid.UUID,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update crawl run status."""
        ...

    async def update_metrics(
        self,
        crawl_run_id: uuid.UUID,
        pages_crawled: int | None = None,
        pages_rendered: int | None = None,
        issues_found: int | None = None,
    ) -> None:
        """Update crawl run metrics."""
        ...

    async def complete(
        self,
        crawl_run_id: uuid.UUID,
        pages_crawled: int,
        pages_rendered: int,
        issues_found: int,
    ) -> None:
        """Mark crawl run as completed."""
        ...

    async def fail(
        self,
        crawl_run_id: uuid.UUID,
        error_message: str,
    ) -> None:
        """Mark crawl run as failed."""
        ...


# Abstract base classes for components that need shared functionality


class BaseFetcher(ABC):
    """Base class for HTTP fetchers."""

    def __init__(
        self,
        user_agent: str = "Openahrush/1.0",
        timeout_ms: int = 30000,
    ) -> None:
        """Initialize fetcher with configuration."""
        self.user_agent = user_agent
        self.timeout_ms = timeout_ms

    @abstractmethod
    async def fetch(self, url: str) -> FetchResult:
        """Fetch a URL."""
        ...

    @abstractmethod
    async def fetch_robots_txt(self, base_url: str) -> str | None:
        """Fetch robots.txt."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close connections."""
        ...


class BaseExtractor(ABC):
    """Base class for HTML extractors."""

    @abstractmethod
    def extract(self, html: bytes, url: str) -> PageData:
        """Extract data from HTML."""
        ...


class BaseRenderer(ABC):
    """Base class for JS renderers."""

    def __init__(self, timeout_ms: int = 30000) -> None:
        """Initialize renderer."""
        self.timeout_ms = timeout_ms

    @abstractmethod
    async def render(self, url: str) -> RenderedResult:
        """Render a page."""
        ...

    @abstractmethod
    async def render_batch(self, urls: list[str]) -> list[RenderedResult]:
        """Render multiple pages."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close browser."""
        ...
