"""
Webhook models for project event notifications.

Provides:
- WebhookConfig: Per-project webhook configuration
- WebhookDelivery: Delivery tracking with retry support
- DeliveryStatus: Enum for delivery states
- VALID_WEBHOOK_EVENTS: List of valid webhook event types
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.project import Project


class DeliveryStatus(str, enum.Enum):
    """Webhook delivery status states."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


# Valid webhook event types based on ARCHITECTURE.md Section 7
VALID_WEBHOOK_EVENTS: list[str] = [
    # Integration events
    "integration.sync_requested",
    "integration.sync_progress",
    "integration.sync_completed",
    "integration.sync_failed",
    # Crawl events
    "crawl.requested",
    "crawl.page_fetched",
    "crawl.js_candidates_selected",
    "crawl.page_rendered",
    "crawl.completed",
    # Audit/rules events
    "rules.completed",
    "diff.completed",
    "alert.fired",
    # Common Crawl events
    "commoncrawl.ingest_requested",
    "commoncrawl.ingest_progress",
    "commoncrawl.ingest_completed",
    "commoncrawl.ingest_failed",
]


class WebhookConfig(Base, UUIDMixin, TimestampMixin):
    """
    Webhook configuration for a project.

    Stores the webhook endpoint URL, secret for HMAC signing,
    and the list of event types this webhook should receive.

    The secret is stored encrypted using Fernet encryption.

    Attributes:
        project_id: UUID of the project this webhook belongs to.
        url: The webhook endpoint URL.
        secret: Encrypted secret for HMAC-SHA256 signing.
        enabled_events: List of event types to deliver to this webhook.
        is_enabled: Whether this webhook is active.
        project: Relationship to the parent project.
        deliveries: Relationship to delivery records.
    """

    __tablename__ = "webhook_configs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    secret: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    enabled_events: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship(
        back_populates="webhook_configs",
    )
    deliveries: Mapped[list[WebhookDelivery]] = relationship(
        back_populates="webhook_config",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def should_deliver(self, event_type: str) -> bool:
        """
        Check if this webhook should receive a given event type.

        Args:
            event_type: The event type to check.

        Returns:
            True if the webhook is enabled and subscribed to this event type.
        """
        return self.is_enabled and event_type in self.enabled_events


class WebhookDelivery(Base):
    """
    Webhook delivery record.

    Tracks individual delivery attempts for a webhook event,
    including retry logic and response information.

    Attributes:
        id: UUID primary key.
        webhook_config_id: UUID of the parent webhook config.
        event_type: The type of event being delivered.
        payload: The full event payload (JSONB).
        delivery_status: Current status (pending, success, failed).
        attempts: Number of delivery attempts made.
        last_attempt_at: Timestamp of the last delivery attempt.
        response_status: HTTP status code from last attempt.
        response_body: Response body from last attempt (truncated).
        next_retry_at: When to retry next (if pending).
        created_at: When this delivery record was created.
        webhook_config: Relationship to parent config.
    """

    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    webhook_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhook_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    delivery_status: Mapped[str] = mapped_column(
        Text,
        default=DeliveryStatus.PENDING.value,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    response_status: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    response_body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    webhook_config: Mapped[WebhookConfig] = relationship(
        back_populates="deliveries",
    )

    @property
    def is_pending(self) -> bool:
        """Check if delivery is still pending."""
        return self.delivery_status == DeliveryStatus.PENDING.value

    @property
    def is_success(self) -> bool:
        """Check if delivery was successful."""
        return self.delivery_status == DeliveryStatus.SUCCESS.value

    @property
    def is_failed(self) -> bool:
        """Check if delivery has permanently failed."""
        return self.delivery_status == DeliveryStatus.FAILED.value
