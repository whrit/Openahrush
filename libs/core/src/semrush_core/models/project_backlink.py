"""
Project backlink model for multi-source backlink storage.

Stores backlinks from multiple sources per project:
- import: CSV imports
- crawl: Discovered during site audits
- commoncrawl: Common Crawl ingestion
- provider: GSC/BWT integrations
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.project import Project


class BacklinkSourceType(str, Enum):
    """Source types for project backlinks."""

    IMPORT = "import"
    CRAWL = "crawl"
    COMMONCRAWL = "commoncrawl"
    PROVIDER = "provider"


class ProjectBacklink(Base, UUIDMixin):
    """
    Project backlink model for unified backlink storage.

    Stores backlinks discovered from various sources, all associated
    with a specific project for unified analysis and reporting.

    Attributes:
        project_id: UUID of the parent project.
        source_url: Full URL of the linking page.
        source_domain: Domain of the linking page.
        target_url: Full URL of the linked page.
        target_domain: Domain of the linked page.
        anchor: Anchor text of the link.
        rel_flags: Link relationship flags (nofollow, ugc, sponsored, etc.).
        source_type: How the backlink was discovered (import, crawl, commoncrawl, provider).
        discovered_at: When the backlink was discovered.
        created_at: When the record was created.
        project: Parent project relationship.
    """

    __tablename__ = "project_backlinks"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "source_url",
            "target_url",
            name="uq_project_backlinks_project_source_target",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
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
    source_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=BacklinkSourceType.IMPORT.value,
        index=True,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship()

    @property
    def is_nofollow(self) -> bool:
        """Check if this link has nofollow attribute."""
        if self.rel_flags is None:
            return False
        return "nofollow" in self.rel_flags

    @property
    def is_dofollow(self) -> bool:
        """Check if this is a dofollow link (no nofollow flag)."""
        return not self.is_nofollow

    @property
    def is_ugc(self) -> bool:
        """Check if this link has ugc (user-generated content) attribute."""
        if self.rel_flags is None:
            return False
        return "ugc" in self.rel_flags

    @property
    def is_sponsored(self) -> bool:
        """Check if this link has sponsored attribute."""
        if self.rel_flags is None:
            return False
        return "sponsored" in self.rel_flags

    @property
    def is_from_import(self) -> bool:
        """Check if this backlink was imported from CSV."""
        return self.source_type == BacklinkSourceType.IMPORT.value

    @property
    def is_from_crawl(self) -> bool:
        """Check if this backlink was discovered during a crawl."""
        return self.source_type == BacklinkSourceType.CRAWL.value

    @property
    def is_from_commoncrawl(self) -> bool:
        """Check if this backlink was discovered via Common Crawl."""
        return self.source_type == BacklinkSourceType.COMMONCRAWL.value

    @property
    def is_from_provider(self) -> bool:
        """Check if this backlink came from a provider (GSC/BWT)."""
        return self.source_type == BacklinkSourceType.PROVIDER.value

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
    def anchor_length(self) -> int:
        """Get the character length of the anchor text."""
        return len(self.anchor) if self.anchor else 0
