"""
SyncJob for integration data synchronization.

Handles synchronization of data from external providers (GSC, GA4, BWT)
to the canonical fact tables. Supports incremental and backfill modes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any, Protocol

from semrush_core.models.sync_run import SyncMode, SyncRun, SyncStatus
from sqlalchemy import select

from semrush_workers.jobs.base import Job, JobType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class DataSyncServiceProtocol(Protocol):
    """Protocol for data sync service dependency."""

    async def sync_data(
        self,
        mapping_id: uuid.UUID,
        date_range_start: date | None,
        date_range_end: date | None,
        sync_mode: SyncMode,
    ) -> dict[str, Any]:
        """Sync data for the given mapping."""
        ...


@dataclass
class SyncJob(Job):
    """
    Job for synchronizing integration data.

    Handles the complete sync lifecycle:
    1. Retrieves or creates SyncRun record
    2. Marks SyncRun as running
    3. Calls DataSyncService to fetch and store data
    4. Updates SyncRun with results (completed/failed)

    Attributes:
        mapping_id: UUID of the integration mapping to sync.
        sync_mode: Sync mode (incremental or backfill).
        date_range_start: Start date for sync range.
        date_range_end: End date for sync range.
        sync_run_id: Optional existing SyncRun ID.
    """

    mapping_id: uuid.UUID = field(default_factory=uuid.uuid4)
    sync_mode: SyncMode = SyncMode.INCREMENTAL
    date_range_start: date | None = None
    date_range_end: date | None = None
    sync_run_id: uuid.UUID | None = None

    @classmethod
    def create(
        cls,
        mapping_id: uuid.UUID,
        sync_mode: SyncMode,
        date_range_start: date | None = None,
        date_range_end: date | None = None,
        sync_run_id: uuid.UUID | None = None,
        max_retries: int = 3,
    ) -> SyncJob:
        """
        Factory method to create a SyncJob.

        Args:
            mapping_id: UUID of the integration mapping.
            sync_mode: Sync mode (incremental or backfill).
            date_range_start: Start date for sync range.
            date_range_end: End date for sync range.
            sync_run_id: Optional existing SyncRun ID.
            max_retries: Maximum retry attempts.

        Returns:
            Configured SyncJob instance.
        """
        job_id = cls.generate_id()

        return cls(
            job_id=job_id,
            job_type=JobType.SYNC if sync_mode == SyncMode.INCREMENTAL else JobType.BACKFILL,
            payload={
                "mapping_id": str(mapping_id),
                "sync_mode": sync_mode.value,
                "date_range_start": date_range_start.isoformat() if date_range_start else None,
                "date_range_end": date_range_end.isoformat() if date_range_end else None,
                "sync_run_id": str(sync_run_id) if sync_run_id else None,
            },
            max_retries=max_retries,
            mapping_id=mapping_id,
            sync_mode=sync_mode,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            sync_run_id=sync_run_id,
        )

    async def execute(
        self,
        db_session: AsyncSession,
        data_sync_service: DataSyncServiceProtocol | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Execute the sync job.

        Args:
            db_session: Database session for persistence.
            data_sync_service: Service for syncing data from providers.

        Returns:
            Result dictionary with success status and records written.
        """
        self.record_attempt()

        try:
            # Get or create SyncRun record
            sync_run = await self._get_or_create_sync_run(db_session)

            # Mark as running
            sync_run.mark_started()
            await db_session.commit()

            if data_sync_service is None:
                raise ValueError("data_sync_service is required")

            # Execute the sync
            result = await data_sync_service.sync_data(
                mapping_id=self.mapping_id,
                date_range_start=self.date_range_start,
                date_range_end=self.date_range_end,
                sync_mode=self.sync_mode,
            )

            records_written = result.get("records_written", 0)

            # Mark as completed
            sync_run.mark_completed(records_written=records_written)
            await db_session.commit()

            self.mark_completed()

            if self.on_success:
                await self.on_success({"success": True, "records_written": records_written})

            return {
                "success": True,
                "records_written": records_written,
                "sync_run_id": str(sync_run.id),
            }

        except Exception as e:
            error_message = str(e)
            self.record_error(error_message)

            # Try to mark SyncRun as failed
            try:
                sync_run = await self._get_sync_run(db_session)  # type: ignore[assignment]
                if sync_run:
                    sync_run.mark_failed(error_message)
                    await db_session.commit()
            except Exception:
                # Best effort - don't fail if we can't update the record
                await db_session.rollback()

            if self.on_failure:
                await self.on_failure(e)

            return {
                "success": False,
                "error": error_message,
            }

    async def _get_or_create_sync_run(
        self,
        db_session: AsyncSession,
    ) -> SyncRun:
        """
        Get existing SyncRun or create a new one.

        Args:
            db_session: Database session.

        Returns:
            SyncRun instance.
        """
        if self.sync_run_id:
            sync_run = await self._get_sync_run(db_session)
            if sync_run:
                return sync_run

        # We need to get the mapping to create a proper SyncRun
        # For now, create with available data
        sync_run = SyncRun(
            integration_mapping_id=self.mapping_id,
            provider="unknown",  # Will be filled by the caller
            property_id="unknown",  # Will be filled by the caller
            mode=self.sync_mode.value,
            status=SyncStatus.QUEUED.value,
            date_range_start=self.date_range_start,
            date_range_end=self.date_range_end,
        )

        db_session.add(sync_run)
        await db_session.commit()
        await db_session.refresh(sync_run)

        self.sync_run_id = sync_run.id  # type: ignore[assignment]
        return sync_run

    async def _get_sync_run(
        self,
        db_session: AsyncSession,
    ) -> SyncRun | None:
        """
        Get existing SyncRun by ID.

        Args:
            db_session: Database session.

        Returns:
            SyncRun instance or None.
        """
        if not self.sync_run_id:
            return None

        result = await db_session.execute(
            select(SyncRun).where(SyncRun.id == self.sync_run_id)
        )
        return result.scalar_one_or_none()

    def to_dict(self) -> dict[str, Any]:
        """Serialize job to dictionary with sync-specific fields."""
        data = super().to_dict()
        data.update({
            "mapping_id": str(self.mapping_id),
            "sync_mode": self.sync_mode.value,
            "date_range_start": self.date_range_start.isoformat() if self.date_range_start else None,
            "date_range_end": self.date_range_end.isoformat() if self.date_range_end else None,
            "sync_run_id": str(self.sync_run_id) if self.sync_run_id else None,
        })
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyncJob:
        """Deserialize SyncJob from dictionary."""
        base = Job.from_dict(data)

        return cls(
            job_id=base.job_id,
            job_type=base.job_type,
            payload=base.payload,
            attempts=base.attempts,
            max_retries=base.max_retries,
            created_at=base.created_at,
            last_error=base.last_error,
            scheduled_at=base.scheduled_at,
            started_at=base.started_at,
            completed_at=base.completed_at,
            mapping_id=uuid.UUID(data["mapping_id"]),
            sync_mode=SyncMode(data["sync_mode"]),
            date_range_start=(
                date.fromisoformat(data["date_range_start"])
                if data.get("date_range_start")
                else None
            ),
            date_range_end=(
                date.fromisoformat(data["date_range_end"])
                if data.get("date_range_end")
                else None
            ),
            sync_run_id=(
                uuid.UUID(data["sync_run_id"])
                if data.get("sync_run_id")
                else None
            ),
        )
