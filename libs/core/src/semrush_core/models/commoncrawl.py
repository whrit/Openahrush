"""
Common Crawl infrastructure models.

Provides models for managing Common Crawl backlink data ingestion:
- CommonCrawlSnapshot: Track Common Crawl snapshots and ingestion status
- CommonCrawlEdge: Raw backlink edges from Common Crawl
- CommonCrawlRefDomain: Aggregated referring domain data
- CommonCrawlAnchor: Aggregated anchor text data

These tables support the Common Crawl ingestion pipeline for
large-scale backlink discovery and analysis.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin


class SnapshotStatus(str, Enum):
    """Common Crawl snapshot ingestion status values."""

    KNOWN = "known"
    INGESTING = "ingesting"
    INGESTED = "ingested"
    FAILED = "failed"


class CommonCrawlSnapshot(Base, UUIDMixin):
    """
    Common Crawl snapshot model for tracking ingestion.

    Each snapshot represents a Common Crawl dataset (e.g., CC-MAIN-2025-05)
    and tracks the ingestion status, progress, and metadata.

    Attributes:
        snapshot_id: Unique Common Crawl snapshot identifier (e.g., 'CC-MAIN-2025-05').
        status: Ingestion status ('known', 'ingesting', 'ingested', 'failed').
        date_range_start: Start date of the crawl period.
        date_range_end: End date of the crawl period.
        spec: JSONB metadata about the snapshot (WARC paths, segment counts, etc.).
        total_records: Total number of records in the snapshot.
        edges_ingested: Number of edges ingested so far.
        ingestion_started_at: When ingestion began.
        ingestion_completed_at: When ingestion finished.
        error_message: Error details if ingestion failed.
        notes: Operator notes about the snapshot.
        created_at: When the snapshot record was created.
        edges: Related CommonCrawlEdge records.
        refdomains: Related CommonCrawlRefDomain records.
        anchors: Related CommonCrawlAnchor records.
    """

    __tablename__ = "commoncrawl_snapshots"

    snapshot_id: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        Text,
        default=SnapshotStatus.KNOWN.value,
        nullable=False,
        index=True,
    )
    date_range_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    date_range_end: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    spec: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    total_records: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    edges_ingested: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    ingestion_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ingestion_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    edges: Mapped[list[CommonCrawlEdge]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    refdomains: Mapped[list[CommonCrawlRefDomain]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    anchors: Mapped[list[CommonCrawlAnchor]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    @property
    def is_known(self) -> bool:
        """Check if this snapshot is in 'known' status."""
        return self.status == SnapshotStatus.KNOWN.value

    @property
    def is_ingesting(self) -> bool:
        """Check if this snapshot is currently being ingested."""
        return self.status == SnapshotStatus.INGESTING.value

    @property
    def is_ingested(self) -> bool:
        """Check if this snapshot has been fully ingested."""
        return self.status == SnapshotStatus.INGESTED.value

    @property
    def is_failed(self) -> bool:
        """Check if this snapshot ingestion failed."""
        return self.status == SnapshotStatus.FAILED.value

    @property
    def ingestion_progress(self) -> float | None:
        """
        Calculate ingestion progress as a percentage.

        Returns:
            Percentage (0-100) of records ingested, or None if total_records unknown.
        """
        if self.total_records is None or self.total_records == 0:
            return None
        edges = self.edges_ingested or 0
        return (edges / self.total_records) * 100


class CommonCrawlEdge(Base, UUIDMixin):
    """
    Common Crawl edge model for raw backlink data.

    Stores individual backlink edges discovered from Common Crawl data.
    Each edge represents a link from a source page to a target page.

    Attributes:
        snapshot_id: Reference to the Common Crawl snapshot.
        source_url: Full URL of the linking page.
        source_domain: Domain of the linking page.
        target_url: Full URL of the linked page.
        target_domain: Domain of the linked page.
        anchor: Anchor text of the link.
        rel_flags: Link relationship flags (nofollow, ugc, sponsored, etc.).
        discovered_at: When the edge was ingested.
        snapshot: Parent CommonCrawlSnapshot relationship.
    """

    __tablename__ = "commoncrawl_edges"

    snapshot_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("commoncrawl_snapshots.snapshot_id", ondelete="CASCADE"),
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
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    snapshot: Mapped[CommonCrawlSnapshot] = relationship(
        back_populates="edges",
    )

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


class CommonCrawlRefDomain(Base, UUIDMixin):
    """
    Common Crawl referring domain aggregation model.

    Stores aggregated data about referring domains for a target domain,
    allowing efficient queries for backlink profile analysis.

    Attributes:
        snapshot_id: Reference to the Common Crawl snapshot.
        target_domain: The domain receiving backlinks.
        source_domain: The domain providing backlinks.
        backlink_count: Number of backlinks from source to target.
        first_seen: When the referring domain was first seen.
        last_seen: When the referring domain was last seen.
        snapshot: Parent CommonCrawlSnapshot relationship.
    """

    __tablename__ = "commoncrawl_refdomains"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "target_domain",
            "source_domain",
            name="uq_commoncrawl_refdomains_snapshot_target_source",
        ),
    )

    snapshot_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("commoncrawl_snapshots.snapshot_id", ondelete="CASCADE"),
        nullable=False,
    )
    target_domain: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    source_domain: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    backlink_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    first_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    snapshot: Mapped[CommonCrawlSnapshot] = relationship(
        back_populates="refdomains",
    )

    @property
    def is_active(self) -> bool:
        """Check if this referring domain relationship is active (has last_seen)."""
        return self.last_seen is not None


class CommonCrawlAnchor(Base, UUIDMixin):
    """
    Common Crawl anchor text aggregation model.

    Stores aggregated anchor text data for a target domain,
    enabling anchor text profile analysis.

    Attributes:
        snapshot_id: Reference to the Common Crawl snapshot.
        target_domain: The domain receiving links with this anchor.
        anchor: The anchor text.
        count: Number of times this anchor text appears.
        snapshot: Parent CommonCrawlSnapshot relationship.
    """

    __tablename__ = "commoncrawl_anchors"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "target_domain",
            "anchor",
            name="uq_commoncrawl_anchors_snapshot_target_anchor",
        ),
    )

    snapshot_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("commoncrawl_snapshots.snapshot_id", ondelete="CASCADE"),
        nullable=False,
    )
    target_domain: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    anchor: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Relationships
    snapshot: Mapped[CommonCrawlSnapshot] = relationship(
        back_populates="anchors",
    )

    @property
    def anchor_length(self) -> int:
        """Get the character length of the anchor text."""
        return len(self.anchor) if self.anchor else 0

    @property
    def is_branded(self) -> bool:
        """
        Check if this anchor text appears to be branded.

        Returns:
            True if the anchor text contains the target domain name.
        """
        if not self.anchor or not self.target_domain:
            return False
        # Extract the main part of the domain (e.g., 'mysite' from 'mysite.com')
        domain_parts = self.target_domain.lower().split(".")
        main_domain = domain_parts[0] if domain_parts else ""
        return (
            main_domain in self.anchor.lower() or self.target_domain.lower() in self.anchor.lower()
        )
