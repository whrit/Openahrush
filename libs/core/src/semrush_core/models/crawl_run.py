"""
Crawl run model for tracking crawl jobs.

Each crawl run represents a complete crawl of a site,
tracking status, configuration, timing, and statistics.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.crawl_page import CrawlPage
    from semrush_core.models.issue_instance import IssueInstance
    from semrush_core.models.link_edge import LinkEdge
    from semrush_core.models.project import Project
    from semrush_core.models.site import Site


class CrawlStatus(str, Enum):
    """Crawl run status values."""

    QUEUED = "queued"
    RUNNING = "running"
    HTML_COMPLETE = "html_complete"
    SELECTING_JS = "selecting_js"
    RENDERING_JS = "rendering_js"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class CrawlRun(Base, UUIDMixin):
    """
    Crawl run model for tracking crawl jobs.

    Each crawl run represents a complete execution of the crawl
    pipeline for a project/site, including HTML fetching, JS
    rendering (when needed), and issue analysis.

    Attributes:
        project_id: UUID of the parent project.
        site_id: Optional UUID of the specific site being crawled.
        status: Current crawl status.
        config_snapshot: ProjectSettings snapshot at crawl time (JSONB).
        started_at: When crawl execution started.
        html_completed_at: When HTML fetching phase completed.
        js_completed_at: When JS rendering phase completed.
        completed_at: When the entire crawl completed.
        stats: Crawl statistics (pages crawled, errors, timing).
        error_message: Error details if crawl failed.
        created_at: When the crawl was queued.
        project: Parent project relationship.
        site: Optional site relationship.
        pages: CrawlPage records for this crawl.
        link_edges: LinkEdge records for this crawl.
        issue_instances: IssueInstance records for this crawl.
    """

    __tablename__ = "crawl_runs"

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
    status: Mapped[str] = mapped_column(
        String(30),
        default=CrawlStatus.QUEUED.value,
        nullable=False,
        index=True,
    )
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    html_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    js_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    stats: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    project: Mapped[Project] = relationship()
    site: Mapped[Site | None] = relationship()
    pages: Mapped[list[CrawlPage]] = relationship(
        back_populates="crawl_run",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    link_edges: Mapped[list[LinkEdge]] = relationship(
        back_populates="crawl_run",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    issue_instances: Mapped[list[IssueInstance]] = relationship(
        back_populates="crawl_run",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    @property
    def is_active(self) -> bool:
        """Check if this crawl is currently active (queued or running)."""
        return self.status in (
            CrawlStatus.QUEUED.value,
            CrawlStatus.RUNNING.value,
            CrawlStatus.HTML_COMPLETE.value,
            CrawlStatus.SELECTING_JS.value,
            CrawlStatus.RENDERING_JS.value,
            CrawlStatus.ANALYZING.value,
        )

    @property
    def is_completed(self) -> bool:
        """Check if this crawl completed successfully."""
        return self.status == CrawlStatus.COMPLETED.value

    @property
    def is_failed(self) -> bool:
        """Check if this crawl failed."""
        return self.status == CrawlStatus.FAILED.value

    @property
    def duration_seconds(self) -> float | None:
        """
        Calculate the crawl duration in seconds.

        Returns:
            Duration in seconds, or None if not applicable.
        """
        if self.started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def mark_started(self) -> None:
        """Mark this crawl as started."""
        from datetime import UTC

        self.status = CrawlStatus.RUNNING.value
        self.started_at = datetime.now(UTC)

    def mark_html_complete(self) -> None:
        """Mark HTML fetching phase as complete."""
        from datetime import UTC

        self.status = CrawlStatus.HTML_COMPLETE.value
        self.html_completed_at = datetime.now(UTC)

    def mark_js_complete(self) -> None:
        """Mark JS rendering phase as complete."""
        from datetime import UTC

        self.status = CrawlStatus.ANALYZING.value
        self.js_completed_at = datetime.now(UTC)

    def mark_completed(self, stats: dict[str, Any] | None = None) -> None:
        """
        Mark this crawl as completed successfully.

        Args:
            stats: Final crawl statistics.
        """
        from datetime import UTC

        self.status = CrawlStatus.COMPLETED.value
        self.completed_at = datetime.now(UTC)
        if stats is not None:
            self.stats = stats

    def mark_failed(self, error_message: str) -> None:
        """
        Mark this crawl as failed.

        Args:
            error_message: Description of what went wrong.
        """
        from datetime import UTC

        self.status = CrawlStatus.FAILED.value
        self.completed_at = datetime.now(UTC)
        self.error_message = error_message
