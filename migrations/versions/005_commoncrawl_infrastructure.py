"""Common Crawl infrastructure tables.

Revision ID: 005_commoncrawl_infrastructure
Revises: 004_crawl_infrastructure
Create Date: 2024-12-28

Creates the Common Crawl infrastructure tables for Sprint 3:
- commoncrawl_snapshots: Track Common Crawl snapshot ingestion status
- commoncrawl_edges: Raw backlink edges from Common Crawl data
- commoncrawl_refdomains: Aggregated referring domain data
- commoncrawl_anchors: Aggregated anchor text data

These tables support the Common Crawl ingestion pipeline for large-scale
backlink discovery and analysis. The design optimizes for:
- High-volume edge ingestion (billions of edges)
- Efficient querying by target domain
- Snapshot-based data isolation for incremental updates
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "005_commoncrawl_infrastructure"
down_revision: str | None = "004_crawl_infrastructure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create commoncrawl_snapshots table
    # Tracks Common Crawl snapshot ingestion status and metadata
    op.create_table(
        "commoncrawl_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            server_default="known",
            nullable=False,
        ),
        sa.Column("date_range_start", sa.Date(), nullable=True),
        sa.Column("date_range_end", sa.Date(), nullable=True),
        sa.Column(
            "spec",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
        sa.Column("total_records", sa.BigInteger(), nullable=True),
        sa.Column("edges_ingested", sa.BigInteger(), nullable=True),
        sa.Column("ingestion_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingestion_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commoncrawl_snapshots")),
        sa.UniqueConstraint("snapshot_id", name=op.f("uq_commoncrawl_snapshots_snapshot_id")),
    )

    # Indexes for commoncrawl_snapshots
    op.create_index(
        "idx_cc_snapshots_status",
        "commoncrawl_snapshots",
        ["status"],
        unique=False,
    )
    op.create_index(
        "idx_cc_snapshots_id",
        "commoncrawl_snapshots",
        ["snapshot_id"],
        unique=False,
    )

    # Create commoncrawl_edges table
    # Raw backlink edges from Common Crawl data
    op.create_table(
        "commoncrawl_edges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_domain", sa.Text(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("target_domain", sa.Text(), nullable=False),
        sa.Column("anchor", sa.Text(), nullable=True),
        sa.Column("rel_flags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["commoncrawl_snapshots.snapshot_id"],
            name=op.f("fk_commoncrawl_edges_snapshot_id_commoncrawl_snapshots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commoncrawl_edges")),
    )

    # Indexes for commoncrawl_edges
    op.create_index(
        "idx_cc_edges_target_domain",
        "commoncrawl_edges",
        ["target_domain"],
        unique=False,
    )
    op.create_index(
        "idx_cc_edges_source_domain",
        "commoncrawl_edges",
        ["source_domain"],
        unique=False,
    )
    op.create_index(
        "idx_cc_edges_snapshot",
        "commoncrawl_edges",
        ["snapshot_id"],
        unique=False,
    )
    # Composite index for efficient querying by target domain and snapshot
    op.create_index(
        "idx_cc_edges_target_domain_snapshot",
        "commoncrawl_edges",
        ["target_domain", "snapshot_id"],
        unique=False,
    )

    # Create commoncrawl_refdomains table
    # Aggregated referring domain data per snapshot
    op.create_table(
        "commoncrawl_refdomains",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("target_domain", sa.Text(), nullable=False),
        sa.Column("source_domain", sa.Text(), nullable=False),
        sa.Column("backlink_count", sa.Integer(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["commoncrawl_snapshots.snapshot_id"],
            name=op.f("fk_commoncrawl_refdomains_snapshot_id_commoncrawl_snapshots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commoncrawl_refdomains")),
        sa.UniqueConstraint(
            "snapshot_id",
            "target_domain",
            "source_domain",
            name="uq_commoncrawl_refdomains_snapshot_target_source",
        ),
    )

    # Index for commoncrawl_refdomains
    op.create_index(
        "idx_cc_refdomains_target",
        "commoncrawl_refdomains",
        ["target_domain"],
        unique=False,
    )

    # Create commoncrawl_anchors table
    # Aggregated anchor text data per snapshot
    op.create_table(
        "commoncrawl_anchors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("target_domain", sa.Text(), nullable=False),
        sa.Column("anchor", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["commoncrawl_snapshots.snapshot_id"],
            name=op.f("fk_commoncrawl_anchors_snapshot_id_commoncrawl_snapshots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commoncrawl_anchors")),
        sa.UniqueConstraint(
            "snapshot_id",
            "target_domain",
            "anchor",
            name="uq_commoncrawl_anchors_snapshot_target_anchor",
        ),
    )

    # Index for commoncrawl_anchors
    op.create_index(
        "idx_cc_anchors_target",
        "commoncrawl_anchors",
        ["target_domain"],
        unique=False,
    )


def downgrade() -> None:
    # Drop commoncrawl_anchors table and index
    op.drop_index("idx_cc_anchors_target", table_name="commoncrawl_anchors")
    op.drop_table("commoncrawl_anchors")

    # Drop commoncrawl_refdomains table and index
    op.drop_index("idx_cc_refdomains_target", table_name="commoncrawl_refdomains")
    op.drop_table("commoncrawl_refdomains")

    # Drop commoncrawl_edges table and indexes
    op.drop_index("idx_cc_edges_target_domain_snapshot", table_name="commoncrawl_edges")
    op.drop_index("idx_cc_edges_snapshot", table_name="commoncrawl_edges")
    op.drop_index("idx_cc_edges_source_domain", table_name="commoncrawl_edges")
    op.drop_index("idx_cc_edges_target_domain", table_name="commoncrawl_edges")
    op.drop_table("commoncrawl_edges")

    # Drop commoncrawl_snapshots table and indexes
    op.drop_index("idx_cc_snapshots_id", table_name="commoncrawl_snapshots")
    op.drop_index("idx_cc_snapshots_status", table_name="commoncrawl_snapshots")
    op.drop_table("commoncrawl_snapshots")
