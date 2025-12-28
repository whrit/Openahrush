"""
Sync run model for tracking data synchronization jobs.

Records the execution history of sync operations between
external providers and the canonical fact tables.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.integration_mapping import IntegrationMapping


class SyncMode(str, Enum):
    """Sync operation modes."""

    BACKFILL = "backfill"
    INCREMENTAL = "incremental"


class SyncStatus(str, Enum):
    """Sync operation status values."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncRun(Base, UUIDMixin):
    """
    Sync run model for tracking data synchronization jobs.

    Each sync run represents a single execution of data synchronization
    from an external provider (GSC, GA4, BWT) to the canonical fact tables.

    Attributes:
        integration_mapping_id: UUID of the integration mapping being synced.
        provider: Provider name (denormalized for query efficiency).
        property_id: Property ID (denormalized for query efficiency).
        mode: Sync mode ('backfill' or 'incremental').
        status: Current status ('queued', 'running', 'completed', 'failed').
        date_range_start: Start of the date range being synced.
        date_range_end: End of the date range being synced.
        records_written: Number of records written to fact tables.
        error_message: Error details if sync failed.
        started_at: When the sync started executing.
        completed_at: When the sync finished (success or failure).
        created_at: When the sync job was created/queued.
        mapping: Parent integration mapping.
    """

    __tablename__ = "sync_runs"

    integration_mapping_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_mappings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    property_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=SyncStatus.QUEUED.value,
        nullable=False,
        index=True,
    )
    date_range_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    date_range_end: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    records_written: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
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
    mapping: Mapped["IntegrationMapping"] = relationship(
        back_populates="sync_runs",
    )

    @property
    def is_active(self) -> bool:
        """Check if this sync run is currently active."""
        return self.status in (SyncStatus.QUEUED.value, SyncStatus.RUNNING.value)

    @property
    def is_completed(self) -> bool:
        """Check if this sync run completed successfully."""
        return self.status == SyncStatus.COMPLETED.value

    @property
    def is_failed(self) -> bool:
        """Check if this sync run failed."""
        return self.status == SyncStatus.FAILED.value

    @property
    def duration_seconds(self) -> float | None:
        """
        Calculate the sync duration in seconds.

        Returns:
            Duration in seconds, or None if not applicable.
        """
        if self.started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def mark_started(self) -> None:
        """Mark this sync as started."""
        from datetime import timezone

        self.status = SyncStatus.RUNNING.value
        self.started_at = datetime.now(timezone.utc)

    def mark_completed(self, records_written: int = 0) -> None:
        """
        Mark this sync as completed successfully.

        Args:
            records_written: Number of records written during sync.
        """
        from datetime import timezone

        self.status = SyncStatus.COMPLETED.value
        self.completed_at = datetime.now(timezone.utc)
        self.records_written = records_written

    def mark_failed(self, error_message: str) -> None:
        """
        Mark this sync as failed.

        Args:
            error_message: Description of what went wrong.
        """
        from datetime import timezone

        self.status = SyncStatus.FAILED.value
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = error_message
