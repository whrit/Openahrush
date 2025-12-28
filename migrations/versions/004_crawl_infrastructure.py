"""Crawl infrastructure tables.

Revision ID: 004_crawl_infrastructure
Revises: 003_fact_tables
Create Date: 2024-12-28

Creates the crawl infrastructure tables for Epic 2.1:
- crawl_runs: Track crawl jobs with status, timing, and configuration
- crawl_pages: Per-page crawl results with SEO fields and artifacts
- link_edges: Internal link graph for link analysis
- issue_types: Issue taxonomy (seeded with MVP issues)
- issue_instances: Per-page issues with confidence and impact scores

These tables enable the core site audit functionality including:
- HTML-first crawling with JS rendering fallback
- Content extraction and hash comparison
- Link graph analysis and broken link detection
- SEO issue detection and reporting
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "004_crawl_infrastructure"
down_revision: str | None = "003_fact_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# MVP Issue Types for seeding
MVP_ISSUE_TYPES = [
    # Content Issues
    {
        "id": "missing_title",
        "category": "content",
        "severity": 4,
        "name": "Missing Title Tag",
        "description": "The page does not have a <title> tag.",
        "recommendation": "Add a unique, descriptive title tag between 50-60 characters.",
    },
    {
        "id": "duplicate_title",
        "category": "content",
        "severity": 3,
        "name": "Duplicate Title Tag",
        "description": "Multiple pages share the same title tag.",
        "recommendation": "Create unique titles for each page that accurately describe the content.",
    },
    {
        "id": "short_title",
        "category": "content",
        "severity": 2,
        "name": "Title Tag Too Short",
        "description": "The title tag is shorter than 30 characters.",
        "recommendation": "Expand the title to 50-60 characters for better visibility in search results.",
    },
    {
        "id": "long_title",
        "category": "content",
        "severity": 2,
        "name": "Title Tag Too Long",
        "description": "The title tag exceeds 60 characters and may be truncated.",
        "recommendation": "Shorten the title to 50-60 characters to prevent truncation.",
    },
    {
        "id": "missing_meta_description",
        "category": "content",
        "severity": 3,
        "name": "Missing Meta Description",
        "description": "The page does not have a meta description.",
        "recommendation": "Add a compelling meta description between 150-160 characters.",
    },
    {
        "id": "duplicate_meta_description",
        "category": "content",
        "severity": 2,
        "name": "Duplicate Meta Description",
        "description": "Multiple pages share the same meta description.",
        "recommendation": "Create unique meta descriptions for each page.",
    },
    {
        "id": "short_meta_description",
        "category": "content",
        "severity": 1,
        "name": "Meta Description Too Short",
        "description": "The meta description is shorter than 70 characters.",
        "recommendation": "Expand the description to 150-160 characters.",
    },
    {
        "id": "long_meta_description",
        "category": "content",
        "severity": 1,
        "name": "Meta Description Too Long",
        "description": "The meta description exceeds 160 characters.",
        "recommendation": "Shorten to 150-160 characters to prevent truncation.",
    },
    {
        "id": "missing_h1",
        "category": "content",
        "severity": 3,
        "name": "Missing H1 Tag",
        "description": "The page does not have an H1 heading.",
        "recommendation": "Add a single, descriptive H1 tag that includes the primary keyword.",
    },
    {
        "id": "multiple_h1",
        "category": "content",
        "severity": 2,
        "name": "Multiple H1 Tags",
        "description": "The page has more than one H1 tag.",
        "recommendation": "Use only one H1 tag per page for clear hierarchy.",
    },
    {
        "id": "thin_content",
        "category": "content",
        "severity": 3,
        "name": "Thin Content",
        "description": "The page has very little text content (under 200 words).",
        "recommendation": "Add more valuable, relevant content to the page.",
    },
    # Technical Issues
    {
        "id": "slow_response",
        "category": "technical",
        "severity": 3,
        "name": "Slow Server Response",
        "description": "The server response time exceeds 500ms.",
        "recommendation": "Optimize server performance, consider caching and CDN.",
    },
    {
        "id": "missing_canonical",
        "category": "technical",
        "severity": 2,
        "name": "Missing Canonical Tag",
        "description": "The page does not have a canonical tag.",
        "recommendation": "Add a canonical tag to prevent duplicate content issues.",
    },
    {
        "id": "canonical_mismatch",
        "category": "technical",
        "severity": 3,
        "name": "Canonical URL Mismatch",
        "description": "The canonical URL points to a different page.",
        "recommendation": "Verify the canonical tag points to the correct URL.",
    },
    {
        "id": "redirect_chain",
        "category": "technical",
        "severity": 3,
        "name": "Redirect Chain",
        "description": "The URL requires multiple redirects to reach the final page.",
        "recommendation": "Update links to point directly to the final URL.",
    },
    {
        "id": "redirect_loop",
        "category": "technical",
        "severity": 5,
        "name": "Redirect Loop",
        "description": "The page is caught in an infinite redirect loop.",
        "recommendation": "Fix the redirect configuration to break the loop.",
    },
    {
        "id": "mixed_content",
        "category": "technical",
        "severity": 3,
        "name": "Mixed Content",
        "description": "HTTPS page loads HTTP resources.",
        "recommendation": "Update all resource URLs to use HTTPS.",
    },
    # Link Issues
    {
        "id": "broken_internal_link",
        "category": "links",
        "severity": 4,
        "name": "Broken Internal Link",
        "description": "An internal link returns a 4xx or 5xx error.",
        "recommendation": "Fix or remove the broken link.",
    },
    {
        "id": "broken_external_link",
        "category": "links",
        "severity": 2,
        "name": "Broken External Link",
        "description": "An external link returns a 4xx or 5xx error.",
        "recommendation": "Remove or update the broken external link.",
    },
    {
        "id": "orphan_page",
        "category": "links",
        "severity": 3,
        "name": "Orphan Page",
        "description": "The page has no internal links pointing to it.",
        "recommendation": "Add internal links from relevant pages.",
    },
    {
        "id": "too_many_links",
        "category": "links",
        "severity": 1,
        "name": "Too Many Links on Page",
        "description": "The page contains more than 100 internal links.",
        "recommendation": "Consider reducing the number of links for better UX.",
    },
    # Indexability Issues
    {
        "id": "noindex",
        "category": "indexability",
        "severity": 1,
        "name": "Page Set to Noindex",
        "description": "The page has a noindex directive.",
        "recommendation": "Verify this is intentional; remove if page should be indexed.",
    },
    {
        "id": "blocked_by_robots",
        "category": "indexability",
        "severity": 2,
        "name": "Blocked by Robots.txt",
        "description": "The page is blocked from crawling by robots.txt.",
        "recommendation": "Update robots.txt if the page should be crawled.",
    },
    {
        "id": "4xx_error",
        "category": "indexability",
        "severity": 4,
        "name": "4xx Client Error",
        "description": "The page returns a 4xx error status code.",
        "recommendation": "Fix the error or implement proper redirects.",
    },
    {
        "id": "5xx_error",
        "category": "indexability",
        "severity": 5,
        "name": "5xx Server Error",
        "description": "The page returns a 5xx server error.",
        "recommendation": "Investigate and fix the server-side error.",
    },
    {
        "id": "soft_404",
        "category": "indexability",
        "severity": 3,
        "name": "Soft 404",
        "description": "The page returns 200 status but appears to be an error page.",
        "recommendation": "Return proper 404 status or redirect to relevant content.",
    },
]


def upgrade() -> None:
    # Create crawl_runs table
    # Tracks crawl jobs with status, timing, configuration, and statistics
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

    # Indexes for crawl_runs
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
        postgresql_using="btree",
        postgresql_ops={"created_at": "DESC"},
    )

    # Create crawl_pages table
    # Per-page crawl results with HTTP response, SEO fields, hashes, and artifacts
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
        # Extracted SEO fields
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
        sa.Column("was_rendered", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("render_trigger", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(
            ["crawl_run_id"],
            ["crawl_runs.id"],
            name=op.f("fk_crawl_pages_crawl_run_id_crawl_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crawl_pages")),
    )

    # Indexes for crawl_pages
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

    # Create link_edges table
    # Internal link graph for link analysis and broken link detection
    op.create_table(
        "link_edges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("crawl_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("anchor_text", sa.Text(), nullable=True),
        sa.Column("is_internal", sa.Boolean(), nullable=False),
        sa.Column("link_type", sa.String(20), nullable=True),
        sa.Column("rel_flags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("is_broken", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("target_status_code", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["crawl_run_id"],
            ["crawl_runs.id"],
            name=op.f("fk_link_edges_crawl_run_id_crawl_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_link_edges")),
    )

    # Indexes for link_edges
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
    # Partial index for broken links (common query pattern)
    op.create_index(
        "idx_link_edges_broken",
        "link_edges",
        ["crawl_run_id", "is_broken"],
        unique=False,
        postgresql_where=sa.text("is_broken = true"),
    )

    # Create issue_types table
    # Issue taxonomy with categories, severity, and recommendations (seeded)
    op.create_table(
        "issue_types",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_issue_types")),
    )

    # Seed issue_types with MVP issues
    issue_types_table = sa.table(
        "issue_types",
        sa.column("id", sa.String),
        sa.column("category", sa.String),
        sa.column("severity", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("recommendation", sa.Text),
    )
    op.bulk_insert(issue_types_table, MVP_ISSUE_TYPES)

    # Create issue_instances table
    # Per-page issues with confidence, impact scores, and evidence
    op.create_table(
        "issue_instances",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("crawl_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("crawl_page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issue_type_id", sa.String(100), nullable=False),
        sa.Column("affected_url", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("impact_score", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
            ["issue_type_id"],
            ["issue_types.id"],
            name=op.f("fk_issue_instances_issue_type_id_issue_types"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_issue_instances")),
    )

    # Indexes for issue_instances
    op.create_index(
        "idx_issue_instances_crawl_run_id",
        "issue_instances",
        ["crawl_run_id"],
        unique=False,
    )
    op.create_index(
        "idx_issue_instances_issue_type_id",
        "issue_instances",
        ["issue_type_id"],
        unique=False,
    )
    op.create_index(
        "idx_issue_instances_impact_score",
        "issue_instances",
        ["impact_score"],
        unique=False,
        postgresql_using="btree",
        postgresql_ops={"impact_score": "DESC NULLS LAST"},
    )
    op.create_index(
        "idx_issue_instances_affected_url",
        "issue_instances",
        ["affected_url"],
        unique=False,
    )


def downgrade() -> None:
    # Drop issue_instances table and indexes
    op.drop_index("idx_issue_instances_affected_url", table_name="issue_instances")
    op.drop_index("idx_issue_instances_impact_score", table_name="issue_instances")
    op.drop_index("idx_issue_instances_issue_type_id", table_name="issue_instances")
    op.drop_index("idx_issue_instances_crawl_run_id", table_name="issue_instances")
    op.drop_table("issue_instances")

    # Drop issue_types table
    op.drop_table("issue_types")

    # Drop link_edges table and indexes
    op.drop_index("idx_link_edges_broken", table_name="link_edges")
    op.drop_index("idx_link_edges_target_url", table_name="link_edges")
    op.drop_index("idx_link_edges_source_url", table_name="link_edges")
    op.drop_index("idx_link_edges_crawl_run_id", table_name="link_edges")
    op.drop_table("link_edges")

    # Drop crawl_pages table and indexes
    op.drop_index("idx_crawl_pages_status_code", table_name="crawl_pages")
    op.drop_index("idx_crawl_pages_url", table_name="crawl_pages")
    op.drop_index("idx_crawl_pages_crawl_run_id", table_name="crawl_pages")
    op.drop_table("crawl_pages")

    # Drop crawl_runs table and indexes
    op.drop_index("idx_crawl_runs_created_at", table_name="crawl_runs")
    op.drop_index("idx_crawl_runs_status", table_name="crawl_runs")
    op.drop_index("idx_crawl_runs_project_id", table_name="crawl_runs")
    op.drop_table("crawl_runs")
