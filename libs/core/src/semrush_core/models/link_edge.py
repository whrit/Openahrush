"""
Link edge model for internal link graph.

Stores all links discovered during a crawl, enabling
internal link analysis and broken link detection.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.crawl_run import CrawlRun


class LinkType(str, Enum):
    """Link type values."""

    A = "a"  # Standard anchor link
    CANONICAL = "canonical"  # Canonical link
    REDIRECT = "redirect"  # Redirect (301, 302, etc.)
    IMG = "img"  # Image source
    SCRIPT = "script"  # Script source


class LinkEdge(Base, UUIDMixin):
    """
    Link edge model for internal link graph.

    Each link edge represents a link discovered during crawling,
    connecting a source URL to a target URL. Used for internal
    link analysis and broken link detection.

    Attributes:
        crawl_run_id: UUID of the parent crawl run.
        source_url: URL of the page containing the link.
        target_url: URL the link points to.
        anchor_text: Link anchor text.
        is_internal: Whether link is internal (same domain).
        link_type: Type of link ('a', 'canonical', 'redirect', 'img', 'script').
        rel_flags: Array of rel attribute values (nofollow, ugc, etc.).
        is_broken: Whether the target returns an error status.
        target_status_code: HTTP status code of target URL.
        crawl_run: Parent crawl run relationship.
    """

    __tablename__ = "link_edges"

    crawl_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    target_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    anchor_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_internal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    link_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    rel_flags: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )
    is_broken: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
    )
    target_status_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Relationships
    crawl_run: Mapped[CrawlRun] = relationship(
        back_populates="link_edges",
    )

    @property
    def is_nofollow(self) -> bool:
        """Check if link has nofollow rel attribute."""
        if self.rel_flags is None:
            return False
        return "nofollow" in self.rel_flags

    @property
    def is_dofollow(self) -> bool:
        """Check if link is dofollow (no nofollow attribute)."""
        return not self.is_nofollow

    @property
    def is_ugc(self) -> bool:
        """Check if link has ugc (user-generated content) attribute."""
        if self.rel_flags is None:
            return False
        return "ugc" in self.rel_flags

    @property
    def is_sponsored(self) -> bool:
        """Check if link has sponsored attribute."""
        if self.rel_flags is None:
            return False
        return "sponsored" in self.rel_flags

    @property
    def is_external(self) -> bool:
        """Check if this is an external link."""
        return not self.is_internal

    @property
    def is_anchor_link(self) -> bool:
        """Check if this is a standard anchor link."""
        return self.link_type == LinkType.A.value

    @property
    def is_canonical_link(self) -> bool:
        """Check if this is a canonical link."""
        return self.link_type == LinkType.CANONICAL.value

    @property
    def is_redirect_link(self) -> bool:
        """Check if this link represents a redirect."""
        return self.link_type == LinkType.REDIRECT.value

    @property
    def anchor_length(self) -> int:
        """Get length of anchor text."""
        if self.anchor_text is None:
            return 0
        return len(self.anchor_text)

    def has_rel_flag(self, flag: str) -> bool:
        """
        Check if link has a specific rel flag.

        Args:
            flag: The rel flag to check for.

        Returns:
            True if flag is present.
        """
        if self.rel_flags is None:
            return False
        return flag in self.rel_flags
