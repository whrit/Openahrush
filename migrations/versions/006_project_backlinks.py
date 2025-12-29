"""Project backlinks table for multi-source backlink storage.

Revision ID: 006_project_backlinks
Revises: 005_commoncrawl_infrastructure
Create Date: 2024-12-28

Creates the project_backlinks table for Sprint 3:
- Stores backlinks from multiple sources per project
- Sources include: import (CSV), crawl, commoncrawl, provider (GSC/BWT)
- Enables unified backlink analysis across all discovery methods

This table complements the existing tables:
- link_facts: General backlink storage with project association
- commoncrawl_edges: Raw Common Crawl data (not project-specific)

The project_backlinks table is project-scoped and tracks backlinks
regardless of their original discovery source.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "006_project_backlinks"
down_revision: str | None = "005_commoncrawl_infrastructure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create project_backlinks table
    # Stores backlinks from multiple sources per project for unified analysis
    op.create_table(
        "project_backlinks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_domain", sa.Text(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("target_domain", sa.Text(), nullable=False),
        sa.Column("anchor", sa.Text(), nullable=True),
        sa.Column("rel_flags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column(
            "source_type",
            sa.Text(),
            server_default="import",
            nullable=False,
        ),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
            name=op.f("fk_project_backlinks_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_backlinks")),
        sa.UniqueConstraint(
            "project_id",
            "source_url",
            "target_url",
            name="uq_project_backlinks_project_source_target",
        ),
    )

    # Create indexes for project_backlinks
    op.create_index(
        "idx_project_backlinks_project",
        "project_backlinks",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "idx_project_backlinks_target",
        "project_backlinks",
        ["target_domain"],
        unique=False,
    )
    op.create_index(
        "idx_project_backlinks_source_domain",
        "project_backlinks",
        ["source_domain"],
        unique=False,
    )
    op.create_index(
        "idx_project_backlinks_source_type",
        "project_backlinks",
        ["source_type"],
        unique=False,
    )
    # Composite index for efficient project + source_type filtering
    op.create_index(
        "idx_project_backlinks_project_source_type",
        "project_backlinks",
        ["project_id", "source_type"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_project_backlinks_project_source_type", table_name="project_backlinks")
    op.drop_index("idx_project_backlinks_source_type", table_name="project_backlinks")
    op.drop_index("idx_project_backlinks_source_domain", table_name="project_backlinks")
    op.drop_index("idx_project_backlinks_target", table_name="project_backlinks")
    op.drop_index("idx_project_backlinks_project", table_name="project_backlinks")

    # Drop table
    op.drop_table("project_backlinks")
