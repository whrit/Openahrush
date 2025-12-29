"""
Project model for organizing SEO work.

Projects contain sites, competitors, and settings. They are the primary
organizational unit for SEO analysis and crawling work.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.alert import Alert
    from semrush_core.models.alert_rule import AlertRule
    from semrush_core.models.competitor import Competitor
    from semrush_core.models.crawl_run import CrawlRun
    from semrush_core.models.settings import ProjectSettings
    from semrush_core.models.site import Site
    from semrush_core.models.user import User
    from semrush_core.models.webhook import WebhookConfig


class Project(Base, UUIDMixin, TimestampMixin):
    """
    Project model representing an SEO project container.

    A project groups together:
    - One or more sites to monitor
    - Competitors to track
    - Project-specific settings for crawling, audits, alerts
    - Crawl runs for site audits
    - Alert rules and alerts
    - Webhook configurations for event notifications

    Attributes:
        owner_id: UUID of the user who owns this project.
        name: Human-readable project name.
        owner: User who owns this project.
        sites: Sites being monitored in this project.
        competitors: Competitor domains being tracked.
        settings: Project-specific settings (one-to-one).
        crawl_runs: Crawl runs for this project.
        alert_rules: Alert rules for this project.
        alerts: Alerts for this project.
        webhook_configs: Webhook configurations for this project.
    """

    __tablename__ = "projects"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Relationships
    owner: Mapped[User] = relationship(
        back_populates="projects",
    )
    sites: Mapped[list[Site]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    competitors: Mapped[list[Competitor]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    settings: Mapped[ProjectSettings | None] = relationship(
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    crawl_runs: Mapped[list[CrawlRun]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    alert_rules: Mapped[list[AlertRule]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    alerts: Mapped[list[Alert]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    webhook_configs: Mapped[list[WebhookConfig]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
