"""
Data models for the crawl orchestration flow.

These dataclasses represent the intermediate data passed between crawl
components: extracted page data, links, render results, and crawl run state.

Note: FetchResult is defined in fetcher.py to avoid circular imports.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class CrawlStatus(StrEnum):
    """Status of a crawl run through its lifecycle."""

    PENDING = "pending"
    RUNNING = "running"
    HTML_COMPLETE = "html_complete"
    JS_RENDERING = "js_rendering"
    JS_COMPLETE = "js_complete"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Link:
    """
    Represents a link extracted from a page.

    Attributes:
        url: Target URL of the link.
        anchor_text: Text content of the anchor element.
        rel_flags: List of rel attribute values (nofollow, sponsored, etc.).
        is_internal: Whether link points to same domain.
    """

    url: str
    anchor_text: str | None = None
    rel_flags: list[str] = field(default_factory=list)
    is_internal: bool = True

    @property
    def is_follow(self) -> bool:
        """Check if link is followable (no nofollow)."""
        return "nofollow" not in self.rel_flags


@dataclass
class PageData:
    """
    Extracted SEO data from a crawled page.

    Contains all SEO-relevant information extracted during parsing,
    including metadata, content metrics, and discovered links.

    Attributes:
        title: Content of the title tag.
        meta_description: Content of meta description tag.
        canonical_url: Canonical URL if specified.
        meta_robots: Meta robots directives (index, follow, etc.).
        h1_count: Number of H1 tags on the page.
        first_h1: Content of the first H1 tag.
        word_count: Approximate word count of text content.
        text_length: Total character count of text content.
        internal_links: Links pointing to same domain.
        external_links: Links pointing to other domains.
        scripts: List of script source URLs.
        html_hash: Hash of the HTML content for change detection.
        og_tags: Open Graph meta tags.
        structured_data: JSON-LD structured data found.
        hreflang_tags: Language/region alternate links.
        load_time_ms: Page load time in milliseconds.
    """

    title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    meta_robots: list[str] = field(default_factory=list)
    h1_count: int = 0
    first_h1: str | None = None
    word_count: int = 0
    text_length: int = 0
    internal_links: list[Link] = field(default_factory=list)
    external_links: list[Link] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    html_hash: str | None = None
    og_tags: dict[str, str] = field(default_factory=dict)
    structured_data: list[dict[str, Any]] = field(default_factory=list)
    hreflang_tags: dict[str, str] = field(default_factory=dict)
    load_time_ms: float = 0.0

    @property
    def is_indexable(self) -> bool:
        """Check if page is indexable based on meta robots."""
        robots_lower = [r.lower() for r in self.meta_robots]
        return "noindex" not in robots_lower

    @property
    def all_links(self) -> list[Link]:
        """Get all links (internal and external)."""
        return self.internal_links + self.external_links


@dataclass
class RenderedResult:
    """
    Result from JavaScript rendering a page.

    Attributes:
        url: URL that was rendered.
        html: Rendered HTML content.
        success: Whether rendering succeeded.
        error: Error message if rendering failed.
        render_time_ms: Time to render in milliseconds.
        console_errors: JavaScript console errors captured.
        network_requests: Count of network requests made.
    """

    url: str
    html: str | None
    success: bool
    error: str | None = None
    render_time_ms: float = 0.0
    console_errors: list[str] = field(default_factory=list)
    network_requests: int = 0


@dataclass
class AnalysisResult:
    """
    Result from running the rules engine on crawled pages.

    Attributes:
        issues_found: Total number of issues detected.
        pages_analyzed: Number of pages analyzed.
        duration_seconds: Time taken to analyze in seconds.
        issues_by_severity: Count of issues by severity level.
        top_issues: List of top issue types found.
    """

    issues_found: int
    pages_analyzed: int
    duration_seconds: float
    issues_by_severity: dict[str, int] = field(default_factory=dict)
    top_issues: list[str] = field(default_factory=list)


@dataclass
class CrawlSettings:
    """
    Settings that control crawl behavior.

    Extracted from project settings with defaults applied.

    Attributes:
        max_pages: Maximum pages to crawl.
        max_depth: Maximum link depth from seed.
        user_agent: User-Agent string for requests.
        render_js: Whether to enable JS rendering.
        js_render_budget: Maximum pages to JS render.
        respect_robots_txt: Whether to respect robots.txt.
        crawl_rate_limit: Max requests per second.
        use_sitemaps: Whether to discover URLs from sitemaps.
        politeness_delay_ms: Delay between requests in milliseconds.
        request_timeout_ms: Request timeout in milliseconds.
    """

    max_pages: int = 500
    max_depth: int = 10
    user_agent: str = "Openahrush/1.0"
    render_js: bool = False
    js_render_budget: int = 50
    respect_robots_txt: bool = True
    crawl_rate_limit: float = 2.0
    use_sitemaps: bool = True
    politeness_delay_ms: int = 500
    request_timeout_ms: int = 30000

    @classmethod
    def from_project_settings(cls, settings_dict: dict[str, Any]) -> CrawlSettings:
        """Create CrawlSettings from project settings dictionary."""
        return cls(
            max_pages=settings_dict.get("max_pages", 500),
            max_depth=settings_dict.get("max_depth", 10),
            user_agent=settings_dict.get("user_agent", "Openahrush/1.0"),
            render_js=settings_dict.get("render_js", False),
            js_render_budget=settings_dict.get("js_render_budget", 50),
            respect_robots_txt=settings_dict.get("respect_robots_txt", True),
            crawl_rate_limit=settings_dict.get("crawl_rate_limit", 2.0),
            use_sitemaps=settings_dict.get("use_sitemaps", True),
            politeness_delay_ms=settings_dict.get("politeness_delay_ms", 500),
            request_timeout_ms=settings_dict.get("request_timeout_ms", 30000),
        )


@dataclass
class CrawlRun:
    """
    Represents an active or completed crawl run.

    Tracks the full lifecycle of a crawl from start to completion,
    including configuration snapshot, progress metrics, and final results.

    Attributes:
        id: Unique identifier for this crawl run.
        project_id: ID of the project being crawled.
        site_id: ID of the site being crawled.
        status: Current status of the crawl.
        config_snapshot: Copy of settings at crawl start.
        seed_url: Starting URL for the crawl.
        started_at: When the crawl started.
        completed_at: When the crawl completed.
        pages_crawled: Number of pages fetched.
        pages_rendered: Number of pages JS-rendered.
        issues_found: Total issues detected.
        error_message: Error message if crawl failed.
    """

    id: uuid.UUID
    project_id: uuid.UUID
    site_id: uuid.UUID
    status: CrawlStatus
    config_snapshot: dict[str, Any]
    seed_url: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    pages_crawled: int = 0
    pages_rendered: int = 0
    issues_found: int = 0
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert crawl run to dictionary for serialization."""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "site_id": str(self.site_id),
            "status": self.status.value,
            "config_snapshot": self.config_snapshot,
            "seed_url": self.seed_url,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "pages_crawled": self.pages_crawled,
            "pages_rendered": self.pages_rendered,
            "issues_found": self.issues_found,
            "error_message": self.error_message,
        }
