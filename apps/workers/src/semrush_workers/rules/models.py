"""
Data models for the Rules Engine.

These models represent crawl data that rules evaluate against.
They are designed to be populated from database queries and
provide a clean interface for rule evaluation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Any


class IssueSeverity(IntEnum):
    """Severity levels for detected issues."""

    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


class DiscoverySource(StrEnum):
    """How a page was discovered during crawling."""

    SEED = "seed"
    SITEMAP = "sitemap"
    INTERNAL_LINK = "internal_link"
    EXTERNAL = "external"


@dataclass
class CrawlPage:
    """
    Represents a crawled page with extracted SEO data.

    Attributes:
        id: Unique identifier for the crawl page record.
        crawl_run_id: ID of the crawl run this page belongs to.
        url: Full URL of the page.
        status_code: HTTP status code returned.
        title: Extracted title tag content.
        meta_description: Extracted meta description content.
        canonical_url: Canonical URL if specified.
        h1_tags: List of H1 tag contents on the page.
        word_count: Approximate word count of page content.
        discovery_source: How this page was discovered.
        redirect_chain: List of URLs in redirect chain if any.
        mixed_content_urls: HTTP resources loaded on HTTPS page.
        is_indexable: Whether the page is indexable.
        crawled_at: When the page was crawled.
    """

    id: uuid.UUID
    crawl_run_id: uuid.UUID
    url: str
    status_code: int
    title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    h1_tags: list[str] = field(default_factory=list)
    word_count: int = 0
    discovery_source: DiscoverySource = DiscoverySource.INTERNAL_LINK
    redirect_chain: list[str] = field(default_factory=list)
    mixed_content_urls: list[str] = field(default_factory=list)
    is_indexable: bool = True
    crawled_at: datetime | None = None

    @property
    def scheme(self) -> str:
        """Extract URL scheme (http or https)."""
        if self.url.startswith("https://"):
            return "https"
        return "http"

    @property
    def domain(self) -> str:
        """Extract domain from URL."""
        url = self.url
        if "://" in url:
            url = url.split("://", 1)[1]
        if "/" in url:
            url = url.split("/", 1)[0]
        return url.lower()

    def is_redirect(self) -> bool:
        """Check if page is a redirect (3xx status)."""
        return 300 <= self.status_code < 400

    def is_client_error(self) -> bool:
        """Check if page returns 4xx status."""
        return 400 <= self.status_code < 500

    def is_server_error(self) -> bool:
        """Check if page returns 5xx status."""
        return 500 <= self.status_code < 600


@dataclass
class LinkEdge:
    """
    Represents a link between two pages.

    Attributes:
        id: Unique identifier for the link edge.
        crawl_run_id: ID of the crawl run this link was found in.
        source_url: URL of the page containing the link.
        target_url: URL the link points to.
        anchor_text: Text content of the link.
        is_internal: Whether the link is internal to the site.
        is_follow: Whether the link passes PageRank (no nofollow).
        target_status_code: Status code of the target page if crawled.
    """

    id: uuid.UUID
    crawl_run_id: uuid.UUID
    source_url: str
    target_url: str
    anchor_text: str | None = None
    is_internal: bool = True
    is_follow: bool = True
    target_status_code: int | None = None

    @property
    def target_domain(self) -> str:
        """Extract domain from target URL."""
        url = self.target_url
        if "://" in url:
            url = url.split("://", 1)[1]
        if "/" in url:
            url = url.split("/", 1)[0]
        return url.lower()


@dataclass
class IssueInstance:
    """
    Represents a detected SEO issue.

    Attributes:
        id: Unique identifier for the issue instance.
        crawl_run_id: ID of the crawl run where issue was found.
        crawl_page_id: ID of the affected crawl page.
        issue_type_id: Identifier of the issue type/rule.
        affected_url: URL where the issue was detected.
        severity: Severity level of the issue.
        confidence: Confidence score (0.0 to 1.0) in detection.
        impact_score: Computed impact score based on severity, confidence, traffic.
        evidence: Dictionary with details about the issue.
        created_at: When the issue was detected.
    """

    id: uuid.UUID
    crawl_run_id: uuid.UUID
    crawl_page_id: uuid.UUID | None
    issue_type_id: str
    affected_url: str
    severity: IssueSeverity
    confidence: float
    impact_score: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert issue to dictionary for serialization."""
        return {
            "id": str(self.id),
            "crawl_run_id": str(self.crawl_run_id),
            "crawl_page_id": str(self.crawl_page_id) if self.crawl_page_id else None,
            "issue_type_id": self.issue_type_id,
            "affected_url": self.affected_url,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "impact_score": self.impact_score,
            "evidence": self.evidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
