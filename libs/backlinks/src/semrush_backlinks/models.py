"""
Backlink data models.

Defines the core data structures for backlink analysis:
- Backlink: Individual link from source to target
- BacklinkSource: Source page metadata
- LinkType: Classification of link types
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class LinkType(StrEnum):
    """Classification of backlink types."""

    DOFOLLOW = "dofollow"
    NOFOLLOW = "nofollow"
    UGC = "ugc"  # User-generated content
    SPONSORED = "sponsored"
    UNKNOWN = "unknown"


class LinkContext(StrEnum):
    """Context where the link appears on the source page."""

    CONTENT = "content"  # Within main content
    NAVIGATION = "navigation"  # In nav/menu
    SIDEBAR = "sidebar"  # In sidebar
    FOOTER = "footer"  # In footer
    HEADER = "header"  # In header
    COMMENT = "comment"  # In comments section
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class BacklinkSource:
    """
    Source page information for a backlink.

    Attributes:
        url: Full URL of the source page.
        domain: Registered domain of source.
        title: Page title if available.
        crawl_date: When the page was crawled.
        language: Detected language code (e.g., "en").
        domain_authority: Estimated domain authority score (0-100).
    """

    url: str
    domain: str
    title: str | None = None
    crawl_date: datetime | None = None
    language: str | None = None
    domain_authority: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "domain": self.domain,
            "title": self.title,
            "crawl_date": self.crawl_date.isoformat() if self.crawl_date else None,
            "language": self.language,
            "domain_authority": self.domain_authority,
        }


@dataclass(frozen=True, slots=True)
class Backlink:
    """
    Individual backlink record.

    Represents a link from a source page to a target URL.
    Includes link attributes, anchor text, and metadata.

    Attributes:
        source: Source page information.
        target_url: URL being linked to.
        anchor_text: Link anchor text.
        link_type: Type of link (dofollow, nofollow, etc.).
        context: Where the link appears on the page.
        first_seen: When this backlink was first discovered.
        last_seen: Most recent crawl that found this link.
        is_image_link: Whether the link is on an image.
        is_redirect: Whether the link goes through a redirect.
        extra_attributes: Additional link attributes (rel values, etc.).
    """

    source: BacklinkSource
    target_url: str
    anchor_text: str = ""
    link_type: LinkType = LinkType.UNKNOWN
    context: LinkContext = LinkContext.UNKNOWN
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    is_image_link: bool = False
    is_redirect: bool = False
    extra_attributes: dict[str, str] = field(default_factory=dict)

    @property
    def source_domain(self) -> str:
        """Get the source domain."""
        return self.source.domain

    @property
    def is_dofollow(self) -> bool:
        """Check if link passes PageRank."""
        return self.link_type == LinkType.DOFOLLOW

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source": self.source.to_dict(),
            "target_url": self.target_url,
            "anchor_text": self.anchor_text,
            "link_type": self.link_type.value,
            "context": self.context.value,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_image_link": self.is_image_link,
            "is_redirect": self.is_redirect,
            "extra_attributes": self.extra_attributes,
        }


@dataclass
class BacklinkProfile:
    """
    Aggregated backlink profile for a domain or URL.

    Summarizes backlink data for analysis and reporting.

    Attributes:
        target: Target domain or URL.
        total_backlinks: Total number of backlinks.
        unique_domains: Number of unique referring domains.
        dofollow_count: Number of dofollow links.
        nofollow_count: Number of nofollow links.
        top_anchors: Most common anchor texts with counts.
        top_domains: Top referring domains with counts.
        last_updated: When this profile was last computed.
    """

    target: str
    total_backlinks: int = 0
    unique_domains: int = 0
    dofollow_count: int = 0
    nofollow_count: int = 0
    top_anchors: list[tuple[str, int]] = field(default_factory=list)
    top_domains: list[tuple[str, int]] = field(default_factory=list)
    last_updated: datetime | None = None

    @property
    def dofollow_ratio(self) -> float:
        """Calculate the ratio of dofollow links."""
        if self.total_backlinks == 0:
            return 0.0
        return self.dofollow_count / self.total_backlinks

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "target": self.target,
            "total_backlinks": self.total_backlinks,
            "unique_domains": self.unique_domains,
            "dofollow_count": self.dofollow_count,
            "nofollow_count": self.nofollow_count,
            "dofollow_ratio": self.dofollow_ratio,
            "top_anchors": self.top_anchors,
            "top_domains": self.top_domains,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }
