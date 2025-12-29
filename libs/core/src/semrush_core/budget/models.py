"""
Database models for resource budget tracking.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.project import Project

# Default budget limits
DEFAULT_MONTHLY_CRAWL_PAGES = 10000
DEFAULT_MONTHLY_EXPORTS = 100

# Warning threshold percentage
WARNING_THRESHOLD_PERCENT = 80.0


class ProjectBudget(Base, UUIDMixin, TimestampMixin):
    """
    Project budget model for tracking resource usage.

    Tracks monthly usage of:
    - Crawl pages (number of pages crawled)
    - Exports (number of export jobs)

    Budget periods are calendar months. Usage resets at the start
    of each new period.
    """

    __tablename__ = "project_budgets"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Budget limits
    monthly_crawl_page_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_MONTHLY_CRAWL_PAGES,
    )
    monthly_export_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_MONTHLY_EXPORTS,
    )

    # Current usage
    crawl_pages_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    exports_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Budget period
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.date_trunc("month", func.now()),
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("date_trunc('month', now()) + interval '1 month'"),
    )

    # Relationships
    project: Mapped[Project] = relationship(back_populates="budget")

    @property
    def crawl_usage_percentage(self) -> float:
        """Calculate crawl usage as a percentage."""
        if self.monthly_crawl_page_limit == 0:
            return 100.0
        return (self.crawl_pages_used / self.monthly_crawl_page_limit) * 100

    @property
    def export_usage_percentage(self) -> float:
        """Calculate export usage as a percentage."""
        if self.monthly_export_limit == 0:
            return 100.0
        return (self.exports_used / self.monthly_export_limit) * 100

    @property
    def is_at_crawl_limit(self) -> bool:
        """Check if crawl limit is reached."""
        return self.crawl_pages_used >= self.monthly_crawl_page_limit

    @property
    def is_at_export_limit(self) -> bool:
        """Check if export limit is reached."""
        return self.exports_used >= self.monthly_export_limit

    @property
    def should_warn_crawl(self) -> bool:
        """Check if crawl usage should trigger a warning."""
        return self.crawl_usage_percentage >= WARNING_THRESHOLD_PERCENT

    @property
    def should_warn_export(self) -> bool:
        """Check if export usage should trigger a warning."""
        return self.export_usage_percentage >= WARNING_THRESHOLD_PERCENT

    @property
    def crawl_pages_remaining(self) -> int:
        """Get remaining crawl pages."""
        return max(0, self.monthly_crawl_page_limit - self.crawl_pages_used)

    @property
    def exports_remaining(self) -> int:
        """Get remaining exports."""
        return max(0, self.monthly_export_limit - self.exports_used)

    def is_period_expired(self) -> bool:
        """Check if the current budget period has expired."""
        return datetime.now(UTC) >= self.period_end
