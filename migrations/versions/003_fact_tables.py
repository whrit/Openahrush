"""Canonical fact tables for analytics data.

Revision ID: 003_fact_tables
Revises: 002_integration_tables
Create Date: 2024-12-28

Creates the canonical fact tables for storing normalized analytics data:
- search_fact_daily: Search console data (GSC, BWT) with query/page metrics
- analytics_fact_daily: Web analytics data (GA4) with session/user metrics
- link_facts: Backlink data from various sources (GSC, BWT, crawls, Common Crawl)

These tables use a unified schema that normalizes data from multiple providers,
enabling consistent querying and aggregation across data sources.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "003_fact_tables"
down_revision: Union[str, None] = "002_integration_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create search_fact_daily table
    # Stores search performance data from GSC and BWT with normalized dimensions
    op.create_table(
        "search_fact_daily",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("engine", sa.Text(), nullable=False),  # 'google', 'bing'
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("device", sa.Text(), nullable=True),  # 'desktop', 'mobile', 'tablet'
        sa.Column("search_type", sa.Text(), nullable=True),  # 'web', 'image', 'video'
        sa.Column("impressions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("clicks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ctr", sa.Numeric(6, 4), nullable=True),  # 0.0000 to 1.0000
        sa.Column("avg_position", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "data_quality_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_search_fact_daily_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name=op.f("fk_search_fact_daily_site_id_sites"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_fact_daily")),
    )

    # Indexes for search_fact_daily
    op.create_index(
        "idx_search_fact_project_date",
        "search_fact_daily",
        ["project_id", "date"],
        unique=False,
    )
    op.create_index(
        "idx_search_fact_query",
        "search_fact_daily",
        ["project_id", "query"],
        unique=False,
        postgresql_where=sa.text("query IS NOT NULL"),
    )
    op.create_index(
        "idx_search_fact_page",
        "search_fact_daily",
        ["project_id", "page_url"],
        unique=False,
        postgresql_where=sa.text("page_url IS NOT NULL"),
    )
    # Unique constraint for deduplication during upserts
    op.create_index(
        "idx_search_fact_unique",
        "search_fact_daily",
        [
            "project_id",
            "engine",
            "date",
            sa.text("COALESCE(query, '')"),
            sa.text("COALESCE(page_url, '')"),
            sa.text("COALESCE(country, '')"),
            sa.text("COALESCE(device, '')"),
        ],
        unique=True,
    )

    # Create analytics_fact_daily table
    # Stores web analytics data from GA4 with normalized dimensions
    op.create_table(
        "analytics_fact_daily",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("device", sa.Text(), nullable=True),
        sa.Column("source_medium", sa.Text(), nullable=True),
        sa.Column("campaign", sa.Text(), nullable=True),
        sa.Column("sessions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("users", sa.Integer(), server_default="0", nullable=True),
        sa.Column("engagement_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("conversions", sa.Integer(), server_default="0", nullable=True),
        sa.Column("revenue", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "data_quality_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_analytics_fact_daily_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name=op.f("fk_analytics_fact_daily_site_id_sites"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analytics_fact_daily")),
    )

    # Indexes for analytics_fact_daily
    op.create_index(
        "idx_analytics_fact_project_date",
        "analytics_fact_daily",
        ["project_id", "date"],
        unique=False,
    )
    op.create_index(
        "idx_analytics_fact_page",
        "analytics_fact_daily",
        ["project_id", "page_url"],
        unique=False,
        postgresql_where=sa.text("page_url IS NOT NULL"),
    )
    # Unique constraint for deduplication during upserts
    op.create_index(
        "idx_analytics_fact_unique",
        "analytics_fact_daily",
        [
            "project_id",
            "date",
            sa.text("COALESCE(page_url, '')"),
            sa.text("COALESCE(country, '')"),
            sa.text("COALESCE(device, '')"),
            sa.text("COALESCE(source_medium, '')"),
        ],
        unique=True,
    )

    # Create link_facts table
    # Stores backlink data from multiple sources (GSC, BWT, crawls, Common Crawl, imports)
    op.create_table(
        "link_facts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source", sa.Text(), nullable=False
        ),  # 'gsc', 'bwt', 'import', 'crawl', 'commoncrawl'
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_domain", sa.Text(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("target_domain", sa.Text(), nullable=False),
        sa.Column("anchor", sa.Text(), nullable=True),
        sa.Column(
            "rel_flags", postgresql.ARRAY(sa.Text()), nullable=True
        ),  # ['nofollow', 'ugc', 'sponsored']
        sa.Column("first_seen", sa.Date(), nullable=True),
        sa.Column("last_seen", sa.Date(), nullable=True),
        sa.Column("snapshot_id", sa.Text(), nullable=True),  # Common Crawl snapshot ID
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_link_facts_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_link_facts")),
    )

    # Indexes for link_facts
    op.create_index(
        "idx_link_facts_project",
        "link_facts",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "idx_link_facts_target_domain",
        "link_facts",
        ["target_domain"],
        unique=False,
    )
    op.create_index(
        "idx_link_facts_source_domain",
        "link_facts",
        ["source_domain"],
        unique=False,
    )
    op.create_index(
        "idx_link_facts_source",
        "link_facts",
        ["source"],
        unique=False,
    )


def downgrade() -> None:
    # Drop link_facts table and indexes
    op.drop_index("idx_link_facts_source", table_name="link_facts")
    op.drop_index("idx_link_facts_source_domain", table_name="link_facts")
    op.drop_index("idx_link_facts_target_domain", table_name="link_facts")
    op.drop_index("idx_link_facts_project", table_name="link_facts")
    op.drop_table("link_facts")

    # Drop analytics_fact_daily table and indexes
    op.drop_index("idx_analytics_fact_unique", table_name="analytics_fact_daily")
    op.drop_index("idx_analytics_fact_page", table_name="analytics_fact_daily")
    op.drop_index("idx_analytics_fact_project_date", table_name="analytics_fact_daily")
    op.drop_table("analytics_fact_daily")

    # Drop search_fact_daily table and indexes
    op.drop_index("idx_search_fact_unique", table_name="search_fact_daily")
    op.drop_index("idx_search_fact_page", table_name="search_fact_daily")
    op.drop_index("idx_search_fact_query", table_name="search_fact_daily")
    op.drop_index("idx_search_fact_project_date", table_name="search_fact_daily")
    op.drop_table("search_fact_daily")
