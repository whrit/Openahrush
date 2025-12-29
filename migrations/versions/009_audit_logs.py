"""Audit logging infrastructure.

Revision ID: 009_audit_logs
Revises: 008_exports_infrastructure
Create Date: 2024-12-28

Creates audit logging infrastructure for security compliance:
- audit_logs: Immutable log of security-sensitive operations

Supports:
- User authentication tracking (login success/failure)
- Integration connection/disconnection tracking
- Project lifecycle auditing
- Export download tracking
- Webhook configuration changes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "009_audit_logs"
down_revision: str | None = "008_exports_infrastructure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create audit_logs table
    # Stores immutable audit entries for security-sensitive operations
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # User who performed the action (nullable for failed logins)
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        # Action type (e.g., "user.login.success", "project.create")
        sa.Column(
            "action",
            sa.String(100),
            nullable=False,
        ),
        # Resource information
        sa.Column(
            "resource_type",
            sa.String(50),
            nullable=True,
        ),
        sa.Column(
            "resource_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        # Action details (flexible JSONB schema)
        sa.Column(
            "details",
            postgresql.JSONB(),
            nullable=True,
        ),
        # Request context
        sa.Column(
            "ip_address",
            sa.String(45),  # IPv6 max length
            nullable=True,
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
        ),
        # Timestamp
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_user_id_users"),
            ondelete="SET NULL",  # Preserve audit logs even if user is deleted
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )

    # Create indexes for common query patterns

    # Index on user_id for user activity queries
    op.create_index(
        "idx_audit_logs_user_id",
        "audit_logs",
        ["user_id"],
        unique=False,
    )

    # Index on action for filtering by action type
    op.create_index(
        "idx_audit_logs_action",
        "audit_logs",
        ["action"],
        unique=False,
    )

    # Index on resource_type for resource queries
    op.create_index(
        "idx_audit_logs_resource_type",
        "audit_logs",
        ["resource_type"],
        unique=False,
    )

    # Index on resource_id for specific resource queries
    op.create_index(
        "idx_audit_logs_resource_id",
        "audit_logs",
        ["resource_id"],
        unique=False,
    )

    # Index on ip_address for security investigations
    op.create_index(
        "idx_audit_logs_ip_address",
        "audit_logs",
        ["ip_address"],
        unique=False,
    )

    # Index on created_at for time-based queries
    op.create_index(
        "idx_audit_logs_created_at",
        "audit_logs",
        ["created_at"],
        unique=False,
        postgresql_using="btree",
    )

    # Composite index for user + time queries
    op.create_index(
        "idx_audit_logs_user_created",
        "audit_logs",
        ["user_id", "created_at"],
        unique=False,
        postgresql_using="btree",
    )

    # Composite index for action + time queries
    op.create_index(
        "idx_audit_logs_action_created",
        "audit_logs",
        ["action", "created_at"],
        unique=False,
        postgresql_using="btree",
    )

    # Composite index for resource queries
    op.create_index(
        "idx_audit_logs_resource",
        "audit_logs",
        ["resource_type", "resource_id", "created_at"],
        unique=False,
        postgresql_using="btree",
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_audit_logs_resource", table_name="audit_logs")
    op.drop_index("idx_audit_logs_action_created", table_name="audit_logs")
    op.drop_index("idx_audit_logs_user_created", table_name="audit_logs")
    op.drop_index("idx_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("idx_audit_logs_ip_address", table_name="audit_logs")
    op.drop_index("idx_audit_logs_resource_id", table_name="audit_logs")
    op.drop_index("idx_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("idx_audit_logs_action", table_name="audit_logs")
    op.drop_index("idx_audit_logs_user_id", table_name="audit_logs")

    # Drop table
    op.drop_table("audit_logs")
