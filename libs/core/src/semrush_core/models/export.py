"""
Export models for tracking export jobs and schedules.

Stores export job metadata and status for CSV, JSON, and PDF exports
with MinIO artifact storage. Also includes scheduled export functionality.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.project import Project


class ExportFormat(str, Enum):
    """Supported export formats."""

    CSV = "csv"
    JSON = "json"
    PDF = "pdf"


class ExportResource(str, Enum):
    """Resources that can be exported."""

    ISSUES = "issues"
    BACKLINKS = "backlinks"
    PAGES = "pages"
    PERFORMANCE = "performance"
    FULL_REPORT = "full_report"


class ExportStatus(str, Enum):
    """Export job status values."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Export(Base, UUIDMixin):
    """
    Export model for tracking export jobs.

    Each export represents a job that generates a file (CSV, JSON, PDF)
    and stores it in MinIO/S3 for download.

    Attributes:
        project_id: UUID of the parent project.
        format: Export format (csv, json, pdf).
        resource: Resource being exported (issues, backlinks, etc.).
        status: Current job status.
        params: Filter/date range parameters.
        artifact_key: MinIO object key for the generated file.
        file_size_bytes: Size of the generated file.
        download_url: Presigned URL for download (expires).
        download_expires_at: When the presigned URL expires.
        error_message: Error message if job failed.
        started_at: When processing started.
        completed_at: When processing completed.
        created_at: When the export was requested.
        project: Parent project relationship.
    """

    __tablename__ = "exports"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    resource: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=ExportStatus.QUEUED.value,
        index=True,
    )
    params: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    artifact_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    download_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    download_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship(back_populates="exports")

    @property
    def is_queued(self) -> bool:
        """Check if export is still queued."""
        return self.status == ExportStatus.QUEUED.value

    @property
    def is_running(self) -> bool:
        """Check if export is currently running."""
        return self.status == ExportStatus.RUNNING.value

    @property
    def is_completed(self) -> bool:
        """Check if export completed successfully."""
        return self.status == ExportStatus.COMPLETED.value

    @property
    def is_failed(self) -> bool:
        """Check if export failed."""
        return self.status == ExportStatus.FAILED.value

    @property
    def is_finished(self) -> bool:
        """Check if export is done (completed or failed)."""
        return self.is_completed or self.is_failed

    @property
    def has_download(self) -> bool:
        """Check if a download URL is available."""
        return self.download_url is not None and self.download_expires_at is not None

    @property
    def is_download_expired(self) -> bool:
        """Check if the download URL has expired."""
        if self.download_expires_at is None:
            return True
        from datetime import UTC

        return datetime.now(UTC) > self.download_expires_at

    @property
    def file_size_mb(self) -> float | None:
        """Get file size in megabytes."""
        if self.file_size_bytes is None:
            return None
        return self.file_size_bytes / (1024 * 1024)

    def get_param(self, key: str, default: Any = None) -> Any:
        """
        Get a parameter value.

        Args:
            key: Parameter key.
            default: Default value if not found.

        Returns:
            Parameter value or default.
        """
        if self.params is None:
            return default
        return self.params.get(key, default)


class ExportSchedule(Base, UUIDMixin):
    """
    Export schedule model for recurring export jobs.

    Allows users to schedule automated exports on a cron schedule.
    Each schedule generates Export records when triggered.

    Attributes:
        project_id: UUID of the parent project.
        format: Export format (csv, json, pdf).
        resource: Resource being exported (issues, backlinks, etc.).
        params: Filter/date range parameters.
        cron_expression: Cron expression for scheduling (e.g., "0 9 * * MON").
        timezone: Timezone for cron evaluation (default: UTC).
        is_enabled: Whether the schedule is active.
        last_run_at: When the schedule was last executed.
        next_run_at: When the schedule will next execute.
        created_at: When the schedule was created.
        project: Parent project relationship.
    """

    __tablename__ = "export_schedules"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    resource: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    params: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    cron_expression: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="UTC",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship(back_populates="export_schedules")

    @property
    def is_active(self) -> bool:
        """Check if schedule is enabled and ready to run."""
        return self.is_enabled

    @property
    def is_due(self) -> bool:
        """Check if the schedule is due to run."""
        if not self.is_enabled or self.next_run_at is None:
            return False
        from datetime import UTC

        return datetime.now(UTC) >= self.next_run_at

    @property
    def has_run(self) -> bool:
        """Check if the schedule has ever been executed."""
        return self.last_run_at is not None

    def get_param(self, key: str, default: Any = None) -> Any:
        """
        Get a parameter value.

        Args:
            key: Parameter key.
            default: Default value if not found.

        Returns:
            Parameter value or default.
        """
        if self.params is None:
            return default
        return self.params.get(key, default)
