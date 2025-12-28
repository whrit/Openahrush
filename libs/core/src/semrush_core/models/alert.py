"""
Alert model for generated alerts.

Stores alerts generated based on alert rules,
including visibility drops, CTR opportunities, and regressions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.alert_rule import AlertRule
    from semrush_core.models.project import Project


class AlertKind(str, Enum):
    """Types of alerts."""

    VISIBILITY_DROP = "visibility_drop"
    CTR_OPPORTUNITY = "ctr_opportunity"
    REGRESSION = "regression"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class AlertEntityType(str, Enum):
    """Types of entities an alert can reference."""

    PROJECT = "project"
    PAGE = "page"
    QUERY = "query"


class Alert(Base, UUIDMixin):
    """
    Alert model for generated alerts.

    Each alert represents a detected condition that
    requires user attention.

    Attributes:
        project_id: UUID of the parent project.
        alert_rule_id: UUID of the rule that triggered this alert.
        kind: Type of alert.
        entity_type: Type of entity the alert references.
        entity_key: Identifier for the referenced entity.
        severity: Alert severity level.
        payload: Additional data as JSONB.
        is_acknowledged: Whether the user has acknowledged the alert.
        created_at: When the alert was generated.
        project: Parent project.
        alert_rule: Rule that triggered this alert.
    """

    __tablename__ = "alerts"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    entity_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    is_acknowledged: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship(back_populates="alerts")
    alert_rule: Mapped[AlertRule | None] = relationship(back_populates="alerts")

    @property
    def is_info(self) -> bool:
        """Check if this is an info-level alert."""
        return self.severity == AlertSeverity.INFO.value

    @property
    def is_warn(self) -> bool:
        """Check if this is a warning-level alert."""
        return self.severity == AlertSeverity.WARN.value

    @property
    def is_critical(self) -> bool:
        """Check if this is a critical alert."""
        return self.severity == AlertSeverity.CRITICAL.value

    def acknowledge(self) -> None:
        """Mark this alert as acknowledged."""
        self.is_acknowledged = True
