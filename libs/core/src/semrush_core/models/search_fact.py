"""
Search fact daily model for search performance data.

Stores normalized daily search metrics from Google Search Console
and Bing Webmaster Tools in a unified schema.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.project import Project
    from semrush_core.models.site import Site


class SearchEngine(str, Enum):
    """Supported search engines."""

    GOOGLE = "google"
    BING = "bing"


class DeviceType(str, Enum):
    """Device types for search metrics."""

    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"


class SearchType(str, Enum):
    """Search types for search metrics."""

    WEB = "web"
    IMAGE = "image"
    VIDEO = "video"
    NEWS = "news"
    DISCOVER = "discover"


class SearchFactDaily(Base, UUIDMixin):
    """
    Search fact daily model for search performance data.

    Stores daily aggregated search metrics from search console integrations
    (GSC, BWT) in a normalized schema that enables cross-engine comparison.

    Dimensions:
    - engine: Search engine source (google, bing)
    - date: Date of the metrics
    - query: Search query (nullable for page-level aggregation)
    - page_url: Page URL (nullable for query-level aggregation)
    - country: ISO country code
    - device: Device type (desktop, mobile, tablet)
    - search_type: Type of search (web, image, video)

    Metrics:
    - impressions: Number of times shown in search results
    - clicks: Number of clicks from search results
    - ctr: Click-through rate (0.0000 to 1.0000)
    - avg_position: Average ranking position

    Attributes:
        project_id: UUID of the parent project.
        site_id: Optional UUID of the associated site.
        engine: Search engine ('google', 'bing').
        date: Date of the metrics.
        query: Search query text.
        page_url: URL of the page.
        country: ISO country code.
        device: Device category.
        search_type: Search type/appearance.
        impressions: Number of impressions.
        clicks: Number of clicks.
        ctr: Click-through rate.
        avg_position: Average position in results.
        data_quality_flags: Quality indicators and sampling info.
        created_at: Record creation timestamp.
    """

    __tablename__ = "search_fact_daily"

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
    engine: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    query: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
    search_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    impressions: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    clicks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    ctr: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4),
        nullable=True,
    )
    avg_position: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
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
    def calculated_ctr(self) -> Decimal | None:
        """
        Calculate CTR from impressions and clicks.

        Returns:
            CTR as a decimal (0.0000 to 1.0000), or None if no impressions.
        """
        if self.impressions == 0:
            return None
        return Decimal(self.clicks) / Decimal(self.impressions)

    @property
    def is_google(self) -> bool:
        """Check if this is Google search data."""
        return self.engine == SearchEngine.GOOGLE.value

    @property
    def is_bing(self) -> bool:
        """Check if this is Bing search data."""
        return self.engine == SearchEngine.BING.value

    @property
    def is_query_level(self) -> bool:
        """Check if this is query-level data."""
        return self.query is not None

    @property
    def is_page_level(self) -> bool:
        """Check if this is page-level data."""
        return self.page_url is not None
