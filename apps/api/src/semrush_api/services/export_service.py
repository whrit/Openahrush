"""
Export service for managing CSV, JSON, and PDF exports.

Provides business logic for:
- Creating export records
- Retrieving export status
- Listing exports for a project
- Updating export status and artifacts
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from semrush_core.models import Export, ExportFormat, ExportResource, ExportStatus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class ExportService:
    """
    Service for managing export operations.

    Handles all export-related business logic including creation,
    retrieval, listing, and status updates.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the export service.

        Args:
            db: Async database session.
        """
        self.db = db

    async def create_export(
        self,
        project_id: uuid.UUID,
        format: ExportFormat,
        resource: ExportResource,
        params: dict[str, Any] | None = None,
    ) -> Export:
        """
        Create a new export record.

        Creates an export job in queued status. The actual export
        processing should be handled by a background worker.

        Args:
            project_id: UUID of the parent project.
            format: Export format (csv, json, pdf).
            resource: Resource to export (issues, backlinks, etc.).
            params: Optional filter/date range parameters.

        Returns:
            Created export record.
        """
        export = Export(
            project_id=project_id,
            format=format.value,
            resource=resource.value,
            status=ExportStatus.QUEUED.value,
            params=params or {},
        )

        self.db.add(export)
        await self.db.commit()
        await self.db.refresh(export)

        return export

    async def get_export(
        self,
        export_id: uuid.UUID,
        project_id: uuid.UUID | None = None,
    ) -> Export | None:
        """
        Get an export by ID.

        Args:
            export_id: Export UUID.
            project_id: Optional project UUID for validation.

        Returns:
            Export if found, None otherwise.
        """
        query = select(Export).where(Export.id == export_id)

        if project_id is not None:
            query = query.where(Export.project_id == project_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_exports(
        self,
        project_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Export], int]:
        """
        List exports for a project with pagination.

        Args:
            project_id: Project UUID.
            limit: Maximum number of exports to return.
            offset: Number of exports to skip.

        Returns:
            Tuple of (list of exports, total count).
        """
        # Get total count
        count_query = select(func.count(Export.id)).where(Export.project_id == project_id)
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated exports
        exports_query = (
            select(Export)
            .where(Export.project_id == project_id)
            .order_by(Export.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(exports_query)
        exports = list(result.scalars().all())

        return exports, total

    async def update_export_status(
        self,
        export_id: uuid.UUID,
        status: ExportStatus,
        artifact_key: str | None = None,
        file_size_bytes: int | None = None,
        download_url: str | None = None,
        download_expires_at: datetime | None = None,
        error_message: str | None = None,
    ) -> Export | None:
        """
        Update export status and related fields.

        Args:
            export_id: Export UUID.
            status: New export status.
            artifact_key: MinIO object key for the generated file.
            file_size_bytes: Size of the generated file.
            download_url: Presigned URL for download.
            download_expires_at: When the presigned URL expires.
            error_message: Error message if job failed.

        Returns:
            Updated export if found, None otherwise.
        """
        export = await self.get_export(export_id)
        if export is None:
            return None

        export.status = status.value

        if status == ExportStatus.RUNNING and export.started_at is None:
            export.started_at = datetime.now(UTC)

        if status in (ExportStatus.COMPLETED, ExportStatus.FAILED):
            export.completed_at = datetime.now(UTC)

        if artifact_key is not None:
            export.artifact_key = artifact_key

        if file_size_bytes is not None:
            export.file_size_bytes = file_size_bytes

        if download_url is not None:
            export.download_url = download_url

        if download_expires_at is not None:
            export.download_expires_at = download_expires_at

        if error_message is not None:
            export.error_message = error_message

        await self.db.commit()
        await self.db.refresh(export)

        return export

    async def mark_export_running(self, export_id: uuid.UUID) -> Export | None:
        """
        Mark an export as running.

        Args:
            export_id: Export UUID.

        Returns:
            Updated export if found, None otherwise.
        """
        return await self.update_export_status(
            export_id=export_id,
            status=ExportStatus.RUNNING,
        )

    async def mark_export_completed(
        self,
        export_id: uuid.UUID,
        artifact_key: str,
        file_size_bytes: int,
        download_url: str,
        expires_hours: int = 168,
    ) -> Export | None:
        """
        Mark an export as completed with artifact information.

        Args:
            export_id: Export UUID.
            artifact_key: MinIO object key for the generated file.
            file_size_bytes: Size of the generated file.
            download_url: Presigned URL for download.
            expires_hours: Hours until download URL expires (default: 168 = 7 days).

        Returns:
            Updated export if found, None otherwise.
        """
        return await self.update_export_status(
            export_id=export_id,
            status=ExportStatus.COMPLETED,
            artifact_key=artifact_key,
            file_size_bytes=file_size_bytes,
            download_url=download_url,
            download_expires_at=datetime.now(UTC) + timedelta(hours=expires_hours),
        )

    async def mark_export_failed(
        self,
        export_id: uuid.UUID,
        error_message: str,
    ) -> Export | None:
        """
        Mark an export as failed with an error message.

        Args:
            export_id: Export UUID.
            error_message: Description of what went wrong.

        Returns:
            Updated export if found, None otherwise.
        """
        return await self.update_export_status(
            export_id=export_id,
            status=ExportStatus.FAILED,
            error_message=error_message,
        )

    async def refresh_download_url(
        self,
        export_id: uuid.UUID,
        new_url: str,
        expires_hours: int = 168,
    ) -> Export | None:
        """
        Refresh the download URL for a completed export.

        Args:
            export_id: Export UUID.
            new_url: New presigned URL.
            expires_hours: Hours until URL expires (default: 168 = 7 days).

        Returns:
            Updated export if found, None otherwise.
        """
        export = await self.get_export(export_id)
        if export is None:
            return None

        if export.status != ExportStatus.COMPLETED.value:
            return None

        export.download_url = new_url
        export.download_expires_at = datetime.now(UTC) + timedelta(hours=expires_hours)

        await self.db.commit()
        await self.db.refresh(export)

        return export

    @staticmethod
    def get_content_type(format: str) -> str:
        """
        Get MIME type for export format.

        Args:
            format: Export format string.

        Returns:
            MIME type string.
        """
        content_types = {
            "csv": "text/csv; charset=utf-8",
            "json": "application/json; charset=utf-8",
            "pdf": "application/pdf",
        }
        return content_types.get(format, "application/octet-stream")

    @staticmethod
    def calculate_progress(status: str) -> float | None:
        """
        Calculate export progress based on status.

        This is a simple estimate. In a real implementation,
        this could be more granular based on actual processing.

        Args:
            status: Export status string.

        Returns:
            Progress percentage (0-100) or None if not applicable.
        """
        if status == ExportStatus.QUEUED.value:
            return 0.0
        elif status == ExportStatus.RUNNING.value:
            return 50.0
        elif status == ExportStatus.COMPLETED.value:
            return 100.0
        elif status == ExportStatus.FAILED.value:
            return None
        return None
