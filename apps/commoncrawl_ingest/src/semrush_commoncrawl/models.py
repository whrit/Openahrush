"""
SQLAlchemy models for Common Crawl ingestion.

Defines the database schema for:
- commoncrawl_snapshots: Snapshot registry and status tracking
- commoncrawl_edges: Raw link edge data
- commoncrawl_refdomains: Aggregated referring domains per target domain
- commoncrawl_anchors: Aggregated anchor text distribution

These tables support the Common Crawl backlink analysis pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from semrush_core.models.base import Base, UUIDMixin
from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column


class SnapshotStatus(StrEnum):
    """Status of a Common Crawl snapshot."""

    KNOWN = "known"
    INGESTING = "ingesting"
    INGESTED = "ingested"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


class CommonCrawlSnapshot(Base, UUIDMixin):
    """
    Common Crawl snapshot registry and status tracking.

    Tracks ingestion status, progress, and aggregate counts
    for each Common Crawl snapshot being processed.

    Attributes:
        snapshot_id: Common Crawl snapshot identifier (e.g., 'CC-MAIN-2024-10').
        status: Current processing status.
        ingested_at: When edge ingestion completed.
        edges_count: Total number of edges ingested.
        refdomains_count: Number of unique referring domain records.
        anchors_count: Number of unique anchor text records.
        aggregates_built_at: When aggregate materialization completed.
        spec_json: Optional JSON spec for subset/filter configuration.
        notes: Optional notes or error messages.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "commoncrawl_snapshots"

    snapshot_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SnapshotStatus.KNOWN.value,
    )
    ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    edges_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    refdomains_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    anchors_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    aggregates_built_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    spec_json: Mapped[str | None] = mapped_column(
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CommonCrawlEdge(Base, UUIDMixin):
    """
    Raw link edge from Common Crawl.

    Stores individual link relationships extracted from Common Crawl data.
    Each edge represents a link from a source URL/domain to a target URL/domain.

    Attributes:
        snapshot_id: Common Crawl snapshot identifier.
        source_url: Full URL of the linking page.
        source_domain: Domain of the linking page.
        target_url: Full URL of the linked page.
        target_domain: Domain of the linked page.
        anchor: Anchor text of the link (may be NULL).
        rel_flags: Relationship flags (nofollow, ugc, sponsored, etc.).
        discovered_at: When this edge was discovered/crawled.
        created_at: Record creation timestamp.
    """

    __tablename__ = "commoncrawl_edges"

    snapshot_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    source_domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    target_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    target_domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    anchor: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    rel_flags: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_commoncrawl_edges_snapshot_target",
            "snapshot_id",
            "target_domain",
        ),
    )


class CommonCrawlRefDomain(Base, UUIDMixin):
    """
    Aggregated referring domain data.

    Stores aggregated counts of backlinks from each source domain
    to each target domain within a snapshot.

    Attributes:
        snapshot_id: Common Crawl snapshot identifier.
        target_domain: Domain receiving the backlinks.
        source_domain: Domain providing the backlinks (referring domain).
        backlink_count: Number of links from source to target.
        first_seen: Earliest discovered_at timestamp for this pair.
        last_seen: Latest discovered_at timestamp for this pair.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "commoncrawl_refdomains"

    snapshot_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    target_domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    source_domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    backlink_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    first_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "target_domain",
            "source_domain",
            name="uq_commoncrawl_refdomains_snapshot_target_source",
        ),
        Index(
            "ix_commoncrawl_refdomains_lookup",
            "snapshot_id",
            "target_domain",
        ),
    )


class CommonCrawlAnchor(Base, UUIDMixin):
    """
    Aggregated anchor text distribution.

    Stores aggregated counts of anchor text occurrences
    for each target domain within a snapshot.

    Attributes:
        snapshot_id: Common Crawl snapshot identifier.
        target_domain: Domain receiving the backlinks.
        anchor: Normalized anchor text.
        count: Number of occurrences of this anchor text.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "commoncrawl_anchors"

    snapshot_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    target_domain: Mapped[str] = mapped_column(
        String(255),
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
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "target_domain",
            "anchor",
            name="uq_commoncrawl_anchors_snapshot_target_anchor",
        ),
        Index(
            "ix_commoncrawl_anchors_lookup",
            "snapshot_id",
            "target_domain",
        ),
    )
