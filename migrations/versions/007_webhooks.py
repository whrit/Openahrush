"""Webhook infrastructure for project event notifications.

Revision ID: 007_webhooks
Revises: 006_project_backlinks
Create Date: 2024-12-28

Creates webhook infrastructure tables:
- webhook_configs: Per-project webhook configuration (URL, secret, enabled events)
- webhook_deliveries: Delivery tracking with retry support

Supports:
- Event filtering per webhook
- At-least-once delivery with exponential backoff
- HMAC-SHA256 signature verification
- Delivery history and debugging
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "007_webhooks"
down_revision: str | None = "006_project_backlinks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create webhook_configs table
    # Stores webhook configuration per project
    op.create_table(
        "webhook_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("secret", sa.Text(), nullable=False),  # Encrypted with Fernet
        sa.Column(
            "enabled_events",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
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
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_webhook_configs_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_configs")),
    )

    # Create indexes for webhook_configs
    op.create_index(
        "idx_webhook_configs_project",
        "webhook_configs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "idx_webhook_configs_enabled",
        "webhook_configs",
        ["project_id", "is_enabled"],
        unique=False,
    )

    # Create webhook_deliveries table
    # Tracks individual webhook delivery attempts
    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("webhook_config_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "delivery_status",
            sa.Text(),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "last_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "response_status",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "response_body",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "next_retry_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["webhook_config_id"],
            ["webhook_configs.id"],
            name=op.f("fk_webhook_deliveries_webhook_config_id_webhook_configs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_deliveries")),
        # Check constraint for valid delivery status
        sa.CheckConstraint(
            "delivery_status IN ('pending', 'success', 'failed')",
            name="ck_webhook_deliveries_valid_status",
        ),
    )

    # Create indexes for webhook_deliveries
    op.create_index(
        "idx_webhook_deliveries_config",
        "webhook_deliveries",
        ["webhook_config_id"],
        unique=False,
    )
    op.create_index(
        "idx_webhook_deliveries_status",
        "webhook_deliveries",
        ["delivery_status"],
        unique=False,
    )
    op.create_index(
        "idx_webhook_deliveries_pending_retry",
        "webhook_deliveries",
        ["delivery_status", "next_retry_at"],
        unique=False,
        postgresql_where=sa.text("delivery_status = 'pending'"),
    )
    op.create_index(
        "idx_webhook_deliveries_created",
        "webhook_deliveries",
        ["webhook_config_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes for webhook_deliveries
    op.drop_index("idx_webhook_deliveries_created", table_name="webhook_deliveries")
    op.drop_index("idx_webhook_deliveries_pending_retry", table_name="webhook_deliveries")
    op.drop_index("idx_webhook_deliveries_status", table_name="webhook_deliveries")
    op.drop_index("idx_webhook_deliveries_config", table_name="webhook_deliveries")

    # Drop webhook_deliveries table
    op.drop_table("webhook_deliveries")

    # Drop indexes for webhook_configs
    op.drop_index("idx_webhook_configs_enabled", table_name="webhook_configs")
    op.drop_index("idx_webhook_configs_project", table_name="webhook_configs")

    # Drop webhook_configs table
    op.drop_table("webhook_configs")
