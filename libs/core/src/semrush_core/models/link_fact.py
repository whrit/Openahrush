"""
Link fact model for backlink data.

Stores backlink information from multiple sources including
GSC, BWT, crawls, imports, and Common Crawl ingestion.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from sqlalchemy import Date, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.project import Project


class LinkSource(str, Enum):
    """Sources of link data."""

    GSC = "gsc"
    BWT = "bwt"
    IMPORT = "import"
    CRAWL = "crawl"
    COMMONCRAWL = "commoncrawl"


class RelFlag(str, Enum):
    """Link relationship flags."""

    NOFOLLOW = "nofollow"
    UGC = "ugc"
    SPONSORED = "sponsored"
    NOOPENER = "noopener"
    NOREFERRER = "noreferrer"


class LinkFact(Base, UUIDMixin):
    """
    Link fact model for backlink data.

    Stores backlink information from various data sources in a
    unified schema that enables comprehensive backlink analysis.

    Attributes:
        project_id: UUID of the parent project.
        source: Data source ('gsc', 'bwt', 'import', 'crawl', 'commoncrawl').
        source_url: Full URL of the linking page.
        source_domain: Domain of the linking page.
        target_url: Full URL of the linked page.
        target_domain: Domain of the linked page.
        anchor: Anchor text of the link.
        rel_flags: Link relationship flags (nofollow, ugc, sponsored).
        first_seen: Date when the link was first discovered.
        last_seen: Date when the link was last seen.
        snapshot_id: Common Crawl snapshot identifier (e.g., 'CC-MAIN-2024-10').
        created_at: Record creation timestamp.
        project: Parent project relationship.
    """

    __tablename__ = "link_facts"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    source_domain: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    target_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    target_domain: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    anchor: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    rel_flags: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )
    first_seen: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    last_seen: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    snapshot_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship()

    @property
    def is_dofollow(self) -> bool:
        """
        Check if this is a dofollow link.

        Returns:
            True if no nofollow flag is present.
        """
        if self.rel_flags is None:
            return True
        return RelFlag.NOFOLLOW.value not in self.rel_flags

    @property
    def is_nofollow(self) -> bool:
        """Check if this link has nofollow attribute."""
        if self.rel_flags is None:
            return False
        return RelFlag.NOFOLLOW.value in self.rel_flags

    @property
    def is_ugc(self) -> bool:
        """Check if this link has ugc (user-generated content) attribute."""
        if self.rel_flags is None:
            return False
        return RelFlag.UGC.value in self.rel_flags

    @property
    def is_sponsored(self) -> bool:
        """Check if this link has sponsored attribute."""
        if self.rel_flags is None:
            return False
        return RelFlag.SPONSORED.value in self.rel_flags

    @property
    def is_internal(self) -> bool:
        """
        Check if this is an internal link.

        Returns:
            True if source and target domains match.
        """
        return self.source_domain.lower() == self.target_domain.lower()

    @property
    def is_external(self) -> bool:
        """
        Check if this is an external link.

        Returns:
            True if source and target domains differ.
        """
        return not self.is_internal

    @property
    def is_from_common_crawl(self) -> bool:
        """Check if this link was discovered via Common Crawl."""
        return self.source == LinkSource.COMMONCRAWL.value

    @property
    def source_path(self) -> str:
        """Extract path from source URL."""
        parsed = urlparse(self.source_url)
        return parsed.path or "/"

    @property
    def target_path(self) -> str:
        """Extract path from target URL."""
        parsed = urlparse(self.target_url)
        return parsed.path or "/"

    @property
    def days_since_first_seen(self) -> int | None:
        """
        Calculate days since the link was first seen.

        Returns:
            Number of days, or None if first_seen is not set.
        """
        if self.first_seen is None:
            return None
        from datetime import date as date_type

        return (date_type.today() - self.first_seen).days

    @property
    def anchor_length(self) -> int:
        """
        Get the length of the anchor text.

        Returns:
            Character count of anchor, or 0 if no anchor.
        """
        if self.anchor is None:
            return 0
        return len(self.anchor)

    def has_rel_flag(self, flag: str | RelFlag) -> bool:
        """
        Check if this link has a specific rel flag.

        Args:
            flag: The rel flag to check.

        Returns:
            True if the flag is present.
        """
        if self.rel_flags is None:
            return False
        flag_value = flag.value if isinstance(flag, RelFlag) else flag
        return flag_value in self.rel_flags
