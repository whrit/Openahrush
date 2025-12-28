"""
Project settings model for project-specific configuration.

Stores crawl schedules, audit rules, alert thresholds, and other
project-level configuration in a flexible JSONB column.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.project import Project


class ProjectSettings(Base, UUIDMixin, TimestampMixin):
    """
    Project settings model for storing project-specific configuration.

    Uses JSONB to store flexible configuration including:
    - Crawl settings (max_pages, user_agent, render_js, etc.)
    - Audit rules and thresholds
    - Alert configurations
    - Integration-specific settings

    Attributes:
        project_id: UUID of the parent project (unique, one-to-one).
        settings: JSONB column storing configuration data.
        project: Parent project these settings belong to.
    """

    __tablename__ = "project_settings"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # Relationships
    project: Mapped[Project] = relationship(
        back_populates="settings",
    )

    def get_crawl_settings(self) -> dict[str, Any]:
        """
        Get crawl-specific settings with defaults.

        Returns:
            Dictionary of crawl settings with sensible defaults.
        """
        defaults = {
            "max_pages": 500,
            "max_depth": 10,
            "user_agent": "Openahrush/1.0",
            "render_js": False,
            "js_render_budget": 50,
            "respect_robots_txt": True,
            "crawl_rate_limit": 2.0,  # requests per second
        }
        crawl_settings = self.settings.get("crawl", {})
        return {**defaults, **crawl_settings}

    def get_audit_settings(self) -> dict[str, Any]:
        """
        Get audit-specific settings with defaults.

        Returns:
            Dictionary of audit settings with sensible defaults.
        """
        defaults = {
            "enabled_rules": [],  # Empty means all rules
            "severity_threshold": "warning",  # info, warning, error, critical
        }
        audit_settings = self.settings.get("audit", {})
        return {**defaults, **audit_settings}

    def get_alert_settings(self) -> dict[str, Any]:
        """
        Get alert-specific settings with defaults.

        Returns:
            Dictionary of alert settings with sensible defaults.
        """
        defaults = {
            "enabled": True,
            "email_notifications": True,
            "webhook_url": None,
        }
        alert_settings = self.settings.get("alerts", {})
        return {**defaults, **alert_settings}
