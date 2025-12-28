"""
Analytics fact daily model for web analytics data.

Stores normalized daily analytics metrics from Google Analytics 4
and other analytics providers in a unified schema.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.project import Project
    from semrush_core.models.site import Site


class AnalyticsFactDaily(Base, UUIDMixin):
    """
    Analytics fact daily model for web analytics data.

    Stores daily aggregated analytics metrics from GA4 and other
    analytics providers in a normalized schema.

    Dimensions:
    - date: Date of the metrics
    - page_url: Page path/URL
    - country: ISO country code
    - device: Device category (desktop, mobile, tablet)
    - source_medium: Traffic source/medium combination
    - campaign: Marketing campaign name

    Metrics:
    - sessions: Number of sessions
    - users: Number of unique users
    - engagement_rate: GA4 engagement rate (0.0000 to 1.0000)
    - conversions: Number of conversion events
    - revenue: Revenue amount (e-commerce)

    Attributes:
        project_id: UUID of the parent project.
        site_id: Optional UUID of the associated site.
        date: Date of the metrics.
        page_url: Page URL/path.
        country: ISO country code.
        device: Device category.
        source_medium: Traffic source and medium.
        campaign: Campaign name.
        sessions: Session count.
        users: User count.
        engagement_rate: Engagement rate.
        conversions: Conversion count.
        revenue: Revenue amount.
        data_quality_flags: Quality indicators and sampling info.
        created_at: Record creation timestamp.
    """

    __tablename__ = "analytics_fact_daily"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="SET NULL"),
        nullable=True,
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    page_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    country: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    device: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    source_medium: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    campaign: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    sessions: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    users: Mapped[int | None] = mapped_column(
        Integer,
        default=0,
        nullable=True,
    )
    engagement_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4),
        nullable=True,
    )
    conversions: Mapped[int | None] = mapped_column(
        Integer,
        default=0,
        nullable=True,
    )
    revenue: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    data_quality_flags: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship()
    site: Mapped[Site | None] = relationship()

    @property
    def source(self) -> str | None:
        """
        Extract traffic source from source_medium.

        Returns:
            Source component or None.
        """
        if self.source_medium is None:
            return None
        parts = self.source_medium.split(" / ", 1)
        return parts[0] if parts else None

    @property
    def medium(self) -> str | None:
        """
        Extract traffic medium from source_medium.

        Returns:
            Medium component or None.
        """
        if self.source_medium is None:
            return None
        parts = self.source_medium.split(" / ", 1)
        return parts[1] if len(parts) > 1 else None

    @property
    def is_organic(self) -> bool:
        """Check if this is organic traffic."""
        medium = self.medium
        return medium is not None and medium.lower() == "organic"

    @property
    def is_paid(self) -> bool:
        """Check if this is paid traffic."""
        medium = self.medium
        if medium is None:
            return False
        return medium.lower() in ("cpc", "ppc", "paid", "paidsearch")

    @property
    def is_direct(self) -> bool:
        """Check if this is direct traffic."""
        source = self.source
        medium = self.medium
        return (
            source is not None
            and medium is not None
            and source.lower() == "(direct)"
            and medium.lower() in ("(none)", "(not set)")
        )

    @property
    def conversion_rate(self) -> Decimal | None:
        """
        Calculate conversion rate from sessions and conversions.

        Returns:
            Conversion rate as a decimal, or None if no sessions.
        """
        if self.sessions == 0 or self.conversions is None:
            return None
        return Decimal(self.conversions) / Decimal(self.sessions)

    @property
    def revenue_per_session(self) -> Decimal | None:
        """
        Calculate revenue per session.

        Returns:
            Revenue per session, or None if no sessions/revenue.
        """
        if self.sessions == 0 or self.revenue is None:
            return None
        return self.revenue / Decimal(self.sessions)
