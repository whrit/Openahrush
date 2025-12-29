"""
Exports endpoints for CSV, JSON, and PDF generation.

Provides endpoints for:
- POST /projects/{id}/exports - Create export job
- GET /projects/{id}/exports - List exports
- GET /projects/{id}/exports/{export_id} - Get export status
- GET /projects/{id}/exports/{export_id}/download - Get download URL
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from semrush_core.models import Export, ExportFormat, ExportResource, ExportStatus, Project
from sqlalchemy import func, select

from semrush_api.deps import CurrentUser, DbSession, Pagination
from semrush_api.schemas.exports import (
    ExportCreate,
    ExportDownload,
    ExportList,
    ExportResponse,
    ExportStatusResponse,
)

router = APIRouter(prefix="/projects/{project_id}/exports", tags=["Exports"])


async def get_user_project(
    db: DbSession,
    project_id: UUID,
    current_user: CurrentUser,
) -> Project:
    """
    Get a project owned by the current user.

    Args:
        db: Database session.
        project_id: Project UUID.
        current_user: Current authenticated user.

    Returns:
        Project if found and owned by user.

    Raises:
        HTTPException: 404 if project not found or not owned by user.
    """
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.user_id,
        )
    )
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project


async def get_export_for_project(
    db: DbSession,
    project_id: UUID,
    export_id: UUID,
) -> Export:
    """
    Get an export belonging to a project.

    Args:
        db: Database session.
        project_id: Project UUID.
        export_id: Export UUID.

    Returns:
        Export if found.

    Raises:
        HTTPException: 404 if export not found.
    """
    result = await db.execute(
        select(Export).where(
            Export.id == export_id,
            Export.project_id == project_id,
        )
    )
    export = result.scalar_one_or_none()

    if export is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found",
        )

    return export


@router.post(
    "",
    response_model=ExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create export",
    description="Create a new export job. Returns immediately with job status.",
)
async def create_export(
    project_id: UUID,
    data: ExportCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ExportResponse:
    """
    Create a new export job.

    The export will be processed asynchronously. Poll the status
    endpoint to check when the export is ready for download.

    Args:
        project_id: Project UUID.
        data: Export creation data.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Created export with queued status.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Create export record
    export = Export(
        project_id=project_id,
        format=data.format.value,
        resource=data.resource.value,
        status=ExportStatus.QUEUED.value,
        params=data.params or {},
    )

    db.add(export)
    await db.commit()
    await db.refresh(export)

    # TODO: Enqueue export job to Redis queue
    # For MVP, we'll process synchronously in a follow-up call
    # await enqueue_export(export.id)

    return ExportResponse.model_validate(export)


@router.get(
    "",
    response_model=ExportList,
    status_code=status.HTTP_200_OK,
    summary="List exports",
    description="List all exports for a project with pagination.",
)
async def list_exports(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    pagination: Pagination,
) -> ExportList:
    """
    List all exports for a project.

    Args:
        project_id: Project UUID.
        db: Database session.
        current_user: Current authenticated user.
        pagination: Pagination parameters.

    Returns:
        Paginated list of exports.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Get total count
    count_result = await db.execute(
        select(func.count(Export.id)).where(Export.project_id == project_id)
    )
    total = count_result.scalar() or 0

    # Get paginated exports
    result = await db.execute(
        select(Export)
        .where(Export.project_id == project_id)
        .order_by(Export.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    exports = result.scalars().all()

    return ExportList(
        items=[ExportResponse.model_validate(e) for e in exports],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{export_id}",
    response_model=ExportStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get export status",
    description="Get the current status of an export job.",
    responses={
        404: {"description": "Export not found"},
    },
)
async def get_export_status(
    project_id: UUID,
    export_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ExportStatusResponse:
    """
    Get the current status of an export.

    Args:
        project_id: Project UUID.
        export_id: Export UUID.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Export status information.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Get export
    export = await get_export_for_project(db, project_id, export_id)

    # Calculate progress (simple estimate based on status)
    progress = None
    if export.status == ExportStatus.QUEUED.value:
        progress = 0.0
    elif export.status == ExportStatus.RUNNING.value:
        progress = 50.0
    elif export.status == ExportStatus.COMPLETED.value:
        progress = 100.0
    elif export.status == ExportStatus.FAILED.value:
        progress = None

    return ExportStatusResponse(
        id=export.id,
        status=export.status,
        progress=progress,
        error_message=export.error_message,
        started_at=export.started_at,
        completed_at=export.completed_at,
        download_url=export.download_url if export.is_completed else None,
    )


@router.get(
    "/{export_id}/download",
    response_model=ExportDownload,
    status_code=status.HTTP_200_OK,
    summary="Get download URL",
    description="Get a presigned download URL for a completed export.",
    responses={
        404: {"description": "Export not found"},
        409: {"description": "Export not yet completed or failed"},
    },
)
async def get_download_url(
    project_id: UUID,
    export_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ExportDownload:
    """
    Get a presigned download URL for a completed export.

    If the download URL has expired, a new one will be generated.

    Args:
        project_id: Project UUID.
        export_id: Export UUID.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Download URL and metadata.

    Raises:
        HTTPException: 409 if export is not completed.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Get export
    export = await get_export_for_project(db, project_id, export_id)

    # Check if export is completed
    if export.status != ExportStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Export is not completed. Current status: {export.status}",
        )

    # Check if download URL is still valid
    if export.download_url and export.download_expires_at:
        if export.download_expires_at > datetime.now(UTC):
            # URL is still valid
            return ExportDownload(
                export_id=export.id,
                download_url=export.download_url,
                expires_at=export.download_expires_at,
                file_size_bytes=export.file_size_bytes,
                content_type=_get_content_type(export.format),
            )

    # URL expired or missing - generate new one
    if export.artifact_key is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export artifact not found",
        )

    # Generate new presigned URL
    try:
        from semrush_reports.storage import ExportStorage

        storage = ExportStorage()
        new_url = await storage.refresh_download_url(export.artifact_key, expires_hours=168)
        new_expires = datetime.now(UTC) + timedelta(hours=168)

        # Update export record
        export.download_url = new_url
        export.download_expires_at = new_expires
        await db.commit()
        await db.refresh(export)

        return ExportDownload(
            export_id=export.id,
            download_url=new_url,
            expires_at=new_expires,
            file_size_bytes=export.file_size_bytes,
            content_type=_get_content_type(export.format),
        )
    except ImportError as err:
        # Storage module not available
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service not available",
        ) from err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {e}",
        ) from e


@router.post(
    "/{export_id}/process",
    response_model=ExportResponse,
    status_code=status.HTTP_200_OK,
    summary="Process export (development)",
    description="Synchronously process an export. For development/testing only.",
    responses={
        404: {"description": "Export not found"},
        409: {"description": "Export already processed or processing"},
    },
)
async def process_export(
    project_id: UUID,
    export_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ExportResponse:
    """
    Synchronously process an export job.

    This endpoint is for development and testing. In production,
    exports should be processed by background workers.

    Args:
        project_id: Project UUID.
        export_id: Export UUID.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Updated export with completed status.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Get export
    export = await get_export_for_project(db, project_id, export_id)

    # Check if export is queued
    if export.status != ExportStatus.QUEUED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Export is not queued. Current status: {export.status}",
        )

    # Update status to running
    export.status = ExportStatus.RUNNING.value
    export.started_at = datetime.now(UTC)
    await db.commit()

    try:
        # Generate export data based on format and resource
        data = await _generate_export_data(db, export)

        # Store export
        from semrush_reports.storage import ExportStorage

        storage = ExportStorage()
        artifact_key, file_size, download_url = await storage.store_export(
            project_id=export.project_id,
            export_id=export.id,
            format=export.format,
            data=data,
        )

        # Update export record
        export.status = ExportStatus.COMPLETED.value
        export.artifact_key = artifact_key
        export.file_size_bytes = file_size
        export.download_url = download_url
        export.download_expires_at = datetime.now(UTC) + timedelta(hours=168)
        export.completed_at = datetime.now(UTC)

    except Exception as e:
        # Mark as failed
        export.status = ExportStatus.FAILED.value
        export.error_message = str(e)
        export.completed_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(export)

    return ExportResponse.model_validate(export)


async def _generate_export_data(db: DbSession, export: Export) -> bytes:
    """Generate export data based on format and resource."""
    format_value = export.format
    resource_value = export.resource
    params = export.params or {}

    if format_value == ExportFormat.CSV.value:
        from semrush_reports.csv_export import CSVExporter

        exporter = CSVExporter()

        if resource_value == ExportResource.ISSUES.value:
            return await exporter.export_issues(
                db,
                export.project_id,
                crawl_run_id=params.get("crawl_run_id"),
                severity_min=params.get("severity_min"),
            )
        elif resource_value == ExportResource.BACKLINKS.value:
            return await exporter.export_backlinks(
                db,
                export.project_id,
                source_type=params.get("source_type"),
                source_domain=params.get("source_domain"),
            )
        elif resource_value == ExportResource.PAGES.value:
            crawl_run_id = params.get("crawl_run_id")
            if not crawl_run_id:
                raise ValueError("crawl_run_id is required for pages export")
            return await exporter.export_pages(
                db,
                crawl_run_id,
                status_code=params.get("status_code"),
            )
        else:
            raise ValueError(f"Unsupported resource for CSV: {resource_value}")

    elif format_value == ExportFormat.JSON.value:
        from semrush_reports.json_export import JSONExporter

        exporter = JSONExporter(pretty=True)

        if resource_value == ExportResource.ISSUES.value:
            return await exporter.export_issues(
                db,
                export.project_id,
                crawl_run_id=params.get("crawl_run_id"),
                severity_min=params.get("severity_min"),
            )
        elif resource_value == ExportResource.BACKLINKS.value:
            return await exporter.export_backlinks(
                db,
                export.project_id,
                source_type=params.get("source_type"),
                source_domain=params.get("source_domain"),
            )
        elif resource_value == ExportResource.PAGES.value:
            crawl_run_id = params.get("crawl_run_id")
            if not crawl_run_id:
                raise ValueError("crawl_run_id is required for pages export")
            return await exporter.export_pages(
                db,
                crawl_run_id,
                status_code=params.get("status_code"),
            )
        elif resource_value == ExportResource.FULL_REPORT.value:
            return await exporter.export_full_report(
                db,
                export.project_id,
                crawl_run_id=params.get("crawl_run_id"),
            )
        else:
            raise ValueError(f"Unsupported resource for JSON: {resource_value}")

    elif format_value == ExportFormat.PDF.value:
        from semrush_reports.pdf_report import PDFReportService

        service = PDFReportService(db)

        if resource_value == ExportResource.ISSUES.value:
            return await service.generate_audit_report(
                export.project_id,
                crawl_run_id=params.get("crawl_run_id"),
            )
        elif resource_value == ExportResource.BACKLINKS.value:
            return await service.generate_backlinks_report(
                export.project_id,
            )
        elif resource_value == ExportResource.FULL_REPORT.value:
            return await service.generate_full_report(
                export.project_id,
                crawl_run_id=params.get("crawl_run_id"),
            )
        else:
            raise ValueError(f"Unsupported resource for PDF: {resource_value}")

    else:
        raise ValueError(f"Unsupported format: {format_value}")


def _get_content_type(format: str) -> str:
    """Get MIME type for export format."""
    content_types = {
        "csv": "text/csv; charset=utf-8",
        "json": "application/json; charset=utf-8",
        "pdf": "application/pdf",
    }
    return content_types.get(format, "application/octet-stream")
