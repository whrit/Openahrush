"""Crawl runs, pages, issues, and alerts tables.

Revision ID: 004_crawl_and_alerts
Revises: 003_fact_tables
Create Date: 2024-12-28

Creates tables for:
- crawl_runs: Track site crawl executions
- crawl_pages: Per-page crawl results
- issue_instances: SEO issues found during crawls
- link_edges: Links discovered during crawls
- alert_rules: User-configured alert rules
- alerts: Generated alerts based on rules
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "004_crawl_and_alerts"
down_revision: Union[str, None] = "003_fact_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create crawl_runs table
    op.create_table(
        "crawl_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            server_default="queued",
            nullable=False,
        ),
        sa.Column(
            "config_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("html_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("js_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "stats",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_crawl_runs_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name=op.f("fk_crawl_runs_site_id_sites"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crawl_runs")),
    )

    op.create_index(
        "idx_crawl_runs_project_id",
        "crawl_runs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "idx_crawl_runs_status",
        "crawl_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "idx_crawl_runs_created_at",
        "crawl_runs",
        ["created_at"],
        unique=False,
    )

    # Create crawl_pages table
    op.create_table(
        "crawl_pages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("crawl_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("render_mode", sa.String(10), nullable=True),
        # SEO fields
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("meta_robots", sa.String(255), nullable=True),
        sa.Column("h1_count", sa.Integer(), nullable=True),
        sa.Column("first_h1", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("text_length", sa.Integer(), nullable=True),
        # Content hashes
        sa.Column("html_hash", sa.String(64), nullable=True),
        sa.Column("rendered_hash", sa.String(64), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        # Artifact references
        sa.Column("html_artifact_key", sa.Text(), nullable=True),
        sa.Column("rendered_artifact_key", sa.Text(), nullable=True),
        # Render tracking
        sa.Column("was_rendered", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("render_trigger", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(
            ["crawl_run_id"],
            ["crawl_runs.id"],
            name=op.f("fk_crawl_pages_crawl_run_id_crawl_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crawl_pages")),
    )

    op.create_index(
        "idx_crawl_pages_crawl_run_id",
        "crawl_pages",
        ["crawl_run_id"],
        unique=False,
    )
    op.create_index(
        "idx_crawl_pages_url",
        "crawl_pages",
        ["url"],
        unique=False,
    )
    op.create_index(
        "idx_crawl_pages_status_code",
        "crawl_pages",
        ["status_code"],
        unique=False,
    )

    # Create issue_instances table
    op.create_table(
        "issue_instances",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("crawl_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("crawl_page_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issue_type_id", sa.String(100), nullable=False),
        sa.Column("affected_url", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 2), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "details",
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
            ["crawl_run_id"],
            ["crawl_runs.id"],
            name=op.f("fk_issue_instances_crawl_run_id_crawl_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["crawl_page_id"],
            ["crawl_pages.id"],
            name=op.f("fk_issue_instances_crawl_page_id_crawl_pages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_issue_instances_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_issue_instances")),
    )

    op.create_index(
        "idx_issue_instances_crawl_run_id",
        "issue_instances",
        ["crawl_run_id"],
        unique=False,
    )
    op.create_index(
        "idx_issue_instances_crawl_page_id",
        "issue_instances",
        ["crawl_page_id"],
        unique=False,
    )
    op.create_index(
        "idx_issue_instances_project_id",
        "issue_instances",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "idx_issue_instances_type_url",
        "issue_instances",
        ["crawl_run_id", "issue_type_id", "affected_url"],
        unique=False,
    )
    op.create_index(
        "idx_issue_instances_severity",
        "issue_instances",
        ["crawl_run_id", "severity"],
        unique=False,
    )
    op.create_index(
        "idx_issue_instances_type_id",
        "issue_instances",
        ["issue_type_id"],
        unique=False,
    )

    # Create link_edges table
    op.create_table(
        "link_edges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("crawl_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_page_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("anchor_text", sa.Text(), nullable=True),
        sa.Column("link_type", sa.String(20), nullable=False),
        sa.Column("is_follow", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("rel_attributes", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["crawl_run_id"],
            ["crawl_runs.id"],
            name=op.f("fk_link_edges_crawl_run_id_crawl_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_page_id"],
            ["crawl_pages.id"],
            name=op.f("fk_link_edges_source_page_id_crawl_pages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_link_edges")),
    )

    op.create_index(
        "idx_link_edges_crawl_run_id",
        "link_edges",
        ["crawl_run_id"],
        unique=False,
    )
    op.create_index(
        "idx_link_edges_source_url",
        "link_edges",
        ["source_url"],
        unique=False,
    )
    op.create_index(
        "idx_link_edges_target_url",
        "link_edges",
        ["target_url"],
        unique=False,
    )

    # Create alert_rules table
    op.create_table(
        "alert_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_alert_rules_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_rules")),
    )

    op.create_index(
        "idx_alert_rules_project_id",
        "alert_rules",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "idx_alert_rules_type",
        "alert_rules",
        ["rule_type"],
        unique=False,
    )

    # Create alerts table
    op.create_table(
        "alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_rule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_key", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_acknowledged",
            sa.Boolean(),
            server_default=sa.text("false"),
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
            name=op.f("fk_alerts_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["alert_rule_id"],
            ["alert_rules.id"],
            name=op.f("fk_alerts_alert_rule_id_alert_rules"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )

    op.create_index(
        "idx_alerts_project_created",
        "alerts",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_alerts_project_severity",
        "alerts",
        ["project_id", "severity"],
        unique=False,
    )
    op.create_index(
        "idx_alerts_kind",
        "alerts",
        ["kind"],
        unique=False,
    )


def downgrade() -> None:
    # Drop alerts table
    op.drop_index("idx_alerts_kind", table_name="alerts")
    op.drop_index("idx_alerts_project_severity", table_name="alerts")
    op.drop_index("idx_alerts_project_created", table_name="alerts")
    op.drop_table("alerts")

    # Drop alert_rules table
    op.drop_index("idx_alert_rules_type", table_name="alert_rules")
    op.drop_index("idx_alert_rules_project_id", table_name="alert_rules")
    op.drop_table("alert_rules")

    # Drop link_edges table
    op.drop_index("idx_link_edges_target_url", table_name="link_edges")
    op.drop_index("idx_link_edges_source_url", table_name="link_edges")
    op.drop_index("idx_link_edges_crawl_run_id", table_name="link_edges")
    op.drop_table("link_edges")

    # Drop issue_instances table
    op.drop_index("idx_issue_instances_type_id", table_name="issue_instances")
    op.drop_index("idx_issue_instances_severity", table_name="issue_instances")
    op.drop_index("idx_issue_instances_type_url", table_name="issue_instances")
    op.drop_index("idx_issue_instances_project_id", table_name="issue_instances")
    op.drop_index("idx_issue_instances_crawl_page_id", table_name="issue_instances")
    op.drop_index("idx_issue_instances_crawl_run_id", table_name="issue_instances")
    op.drop_table("issue_instances")

    # Drop crawl_pages table
    op.drop_index("idx_crawl_pages_status_code", table_name="crawl_pages")
    op.drop_index("idx_crawl_pages_url", table_name="crawl_pages")
    op.drop_index("idx_crawl_pages_crawl_run_id", table_name="crawl_pages")
    op.drop_table("crawl_pages")

    # Drop crawl_runs table
    op.drop_index("idx_crawl_runs_created_at", table_name="crawl_runs")
    op.drop_index("idx_crawl_runs_status", table_name="crawl_runs")
    op.drop_index("idx_crawl_runs_project_id", table_name="crawl_runs")
    op.drop_table("crawl_runs")
