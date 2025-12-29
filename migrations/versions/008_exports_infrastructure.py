"""Exports infrastructure for CSV/JSON/PDF generation and scheduling.

Revision ID: 008_exports_infrastructure
Revises: 007_webhooks
Create Date: 2024-12-28

Creates export infrastructure tables:
- exports: Export job tracking with MinIO artifact storage
- export_schedules: Recurring export configuration with cron support

Supports:
- CSV, JSON, and PDF export formats
- Multiple resource types (issues, backlinks, pages, performance, full_report)
- Scheduled exports with cron expressions
- Download URL generation with expiration
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "008_exports_infrastructure"
down_revision: str | None = "007_webhooks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create exports table
    # Tracks export jobs with status, artifact storage, and download URLs
    op.create_table(
        "exports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),  # csv, json, pdf
        sa.Column(
            "resource", sa.Text(), nullable=False
        ),  # issues, backlinks, pages, performance, full_report
        sa.Column(
            "status",
            sa.Text(),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),  # queued, running, completed, failed
        sa.Column(
            "params",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
        sa.Column("artifact_key", sa.Text(), nullable=True),  # MinIO object key
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.Column("download_expires_at", sa.DateTime(timezone=True), nullable=True),
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
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_exports_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exports")),
    )

    # Create indexes for exports
    op.create_index(
        "idx_exports_project",
        "exports",
        ["project_id", "created_at"],
        unique=False,
        postgresql_using="btree",
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "idx_exports_status",
        "exports",
        ["status"],
        unique=False,
    )

    # Create export_schedules table
    # Stores recurring export configurations with cron scheduling
    op.create_table(
        "export_schedules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),  # csv, json, pdf
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
        sa.Column("cron_expression", sa.Text(), nullable=False),
        sa.Column(
            "timezone",
            sa.String(64),
            server_default=sa.text("'UTC'"),
            nullable=False,
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_export_schedules_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_export_schedules")),
    )

    # Create indexes for export_schedules
    op.create_index(
        "idx_export_schedules_project",
        "export_schedules",
        ["project_id"],
        unique=False,
    )
    # Partial index for efficient next_run_at queries on enabled schedules
    op.create_index(
        "idx_export_schedules_next",
        "export_schedules",
        ["next_run_at"],
        unique=False,
        postgresql_where=sa.text("is_enabled = true"),
    )


def downgrade() -> None:
    # Drop indexes for export_schedules
    op.drop_index("idx_export_schedules_next", table_name="export_schedules")
    op.drop_index("idx_export_schedules_project", table_name="export_schedules")

    # Drop export_schedules table
    op.drop_table("export_schedules")

    # Drop indexes for exports
    op.drop_index("idx_exports_status", table_name="exports")
    op.drop_index("idx_exports_project", table_name="exports")

    # Drop exports table
    op.drop_table("exports")
