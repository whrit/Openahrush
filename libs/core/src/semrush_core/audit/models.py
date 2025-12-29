"""
Audit logging models.

Provides SQLAlchemy models for tracking security-sensitive operations:
- User authentication (login/logout)
- Integration connections/disconnections
- Project creation/deletion
- Export downloads
- Webhook changes
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.user import User


class AuditAction(str, enum.Enum):
    """
    Enumeration of auditable actions.

    Actions are namespaced by resource type:
    - user.*: Authentication-related actions
    - integration.*: OAuth integration actions
    - project.*: Project lifecycle actions
    - export.*: Export/download actions
    - webhook.*: Webhook configuration actions
    """

    # Authentication actions
    LOGIN_SUCCESS = "user.login.success"
    LOGIN_FAILED = "user.login.failed"
    LOGOUT = "user.logout"
    PASSWORD_CHANGE = "user.password.change"
    PASSWORD_RESET = "user.password.reset"

    # Integration actions
    INTEGRATION_CONNECT = "integration.connect"
    INTEGRATION_DISCONNECT = "integration.disconnect"
    INTEGRATION_REFRESH = "integration.refresh"

    # Project actions
    PROJECT_CREATE = "project.create"
    PROJECT_UPDATE = "project.update"
    PROJECT_DELETE = "project.delete"

    # Export actions
    EXPORT_CREATE = "export.create"
    EXPORT_DOWNLOAD = "export.download"

    # Webhook actions
    WEBHOOK_CREATE = "webhook.create"
    WEBHOOK_UPDATE = "webhook.update"
    WEBHOOK_DELETE = "webhook.delete"

    # API key actions (for future use)
    API_KEY_CREATE = "api_key.create"
    API_KEY_REVOKE = "api_key.revoke"


class AuditLog(Base, UUIDMixin):
    """
    Audit log entry for security-sensitive operations.

    Records who did what, when, and from where. Designed as an append-only
    log for compliance and security forensics.

    Attributes:
        id: UUID primary key.
        user_id: UUID of the user who performed the action (nullable for failed logins).
        action: The action type (from AuditAction enum or custom string).
        resource_type: Type of resource affected (e.g., "project", "webhook").
        resource_id: UUID of the affected resource (if applicable).
        details: JSONB containing action-specific details.
        ip_address: Client IP address (supports IPv4 and IPv6).
        user_agent: Client user agent string.
        created_at: Timestamp when the action occurred.
    """

    __tablename__ = "audit_logs"

    # Reference to user (nullable for failed login attempts)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Action performed
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    # Resource information (optional)
    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Action details (JSONB for flexible schema)
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Request context
    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
        index=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamp (server-side default)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped[User | None] = relationship(
        "User",
        lazy="selectin",
    )

    # Composite indexes for common query patterns
    __table_args__ = (
        Index("idx_audit_logs_user_created", "user_id", "created_at"),
        Index("idx_audit_logs_action_created", "action", "created_at"),
        Index(
            "idx_audit_logs_resource",
            "resource_type",
            "resource_id",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        """Generate a readable string representation."""
        return (
            f"<AuditLog(id={self.id}, "
            f"action={self.action!r}, "
            f"user_id={self.user_id}, "
            f"created_at={self.created_at})>"
        )
