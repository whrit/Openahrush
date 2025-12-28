"""Integration infrastructure tables.

Revision ID: 002_integration_tables
Revises: 001_initial_schema
Create Date: 2024-12-28

Creates the integration infrastructure tables including:
- integration_tokens: Encrypted OAuth tokens (separate from accounts for security)
- integration_properties: Discovered properties from providers (GSC sites, GA4 properties)
- integration_mappings: Links properties to projects/sites
- sync_runs: Tracks sync job history and status
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "002_integration_tables"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create integration_tokens table
    # Stores encrypted OAuth tokens separately from integration_accounts for security isolation
    op.create_table(
        "integration_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("integration_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("token_type", sa.Text(), server_default="Bearer", nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["integration_account_id"],
            ["integration_accounts.id"],
            name=op.f("fk_integration_tokens_integration_account_id_integration_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_tokens")),
    )
    op.create_index(
        "idx_integration_tokens_account",
        "integration_tokens",
        ["integration_account_id"],
        unique=True,
    )

    # Create integration_properties table
    # Stores discovered properties from OAuth providers (e.g., GSC sites, GA4 properties)
    op.create_table(
        "integration_properties",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("integration_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("property_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("property_type", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["integration_account_id"],
            ["integration_accounts.id"],
            name=op.f("fk_integration_properties_integration_account_id_integration_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_properties")),
        sa.UniqueConstraint(
            "integration_account_id",
            "provider",
            "property_id",
            name="uq_integration_properties_account_provider_property",
        ),
    )
    op.create_index(
        "idx_integration_properties_account",
        "integration_properties",
        ["integration_account_id"],
        unique=False,
    )

    # Create integration_mappings table
    # Links integration properties to projects and optionally specific sites
    op.create_table(
        "integration_mappings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("integration_property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_integration_mappings_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name=op.f("fk_integration_mappings_site_id_sites"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["integration_property_id"],
            ["integration_properties.id"],
            name=op.f("fk_integration_mappings_integration_property_id_integration_properties"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_mappings")),
        sa.UniqueConstraint(
            "project_id",
            "integration_property_id",
            name="uq_integration_mappings_project_property",
        ),
    )
    op.create_index(
        "idx_integration_mappings_project",
        "integration_mappings",
        ["project_id"],
        unique=False,
    )

    # Create sync_runs table
    # Tracks sync job execution history and status
    op.create_table(
        "sync_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("integration_mapping_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("property_id", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),  # 'backfill', 'incremental'
        sa.Column(
            "status",
            sa.Text(),
            server_default="queued",
            nullable=False,
        ),  # queued, running, completed, failed
        sa.Column("date_range_start", sa.Date(), nullable=True),
        sa.Column("date_range_end", sa.Date(), nullable=True),
        sa.Column("records_written", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["integration_mapping_id"],
            ["integration_mappings.id"],
            name=op.f("fk_sync_runs_integration_mapping_id_integration_mappings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_runs")),
    )
    op.create_index(
        "idx_sync_runs_mapping",
        "sync_runs",
        ["integration_mapping_id"],
        unique=False,
    )
    op.create_index(
        "idx_sync_runs_status",
        "sync_runs",
        ["status"],
        unique=False,
    )

    # Apply updated_at triggers to new tables
    for table_name in ["integration_tokens"]:
        op.execute(f"""
            CREATE TRIGGER update_{table_name}_updated_at
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_integration_tokens_updated_at ON integration_tokens")

    # Drop tables in reverse order (respecting foreign key dependencies)
    op.drop_index("idx_sync_runs_status", table_name="sync_runs")
    op.drop_index("idx_sync_runs_mapping", table_name="sync_runs")
    op.drop_table("sync_runs")

    op.drop_index("idx_integration_mappings_project", table_name="integration_mappings")
    op.drop_table("integration_mappings")

    op.drop_index("idx_integration_properties_account", table_name="integration_properties")
    op.drop_table("integration_properties")

    op.drop_index("idx_integration_tokens_account", table_name="integration_tokens")
    op.drop_table("integration_tokens")
