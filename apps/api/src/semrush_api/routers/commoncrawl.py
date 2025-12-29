"""
Common Crawl API endpoints.

Provides endpoints for:
- Listing and viewing Common Crawl snapshots
- Registering new snapshots
- Triggering ingestion
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from semrush_core.models.commoncrawl import CommonCrawlSnapshot, SnapshotStatus
from sqlalchemy import select

from semrush_api.deps import CurrentUser, DbSession
from semrush_api.schemas.commoncrawl import (
    CreateSnapshotRequest,
    IngestRequest,
    IngestResponse,
    SnapshotListResponse,
    SnapshotResponse,
)

router = APIRouter(prefix="/commoncrawl", tags=["Common Crawl"])


@router.get(
    "/snapshots",
    response_model=SnapshotListResponse,
    status_code=status.HTTP_200_OK,
    summary="List snapshots",
    description="List all Common Crawl snapshots with optional status filtering.",
)
async def list_snapshots(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Annotated[
        SnapshotStatus | None,
        Query(alias="status", description="Filter by snapshot status"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum number of results"),
    ] = 20,
) -> SnapshotListResponse:
    """
    List all Common Crawl snapshots.

    Returns list of snapshots with their status and ingestion progress.
    Supports filtering by status and pagination via limit.

    Args:
        db: Database session.
        current_user: Current authenticated user.
        status_filter: Optional status filter (known, ingesting, ingested, failed).
        limit: Maximum number of results (default 20, max 100).

    Returns:
        List of snapshot records.
    """
    query = select(CommonCrawlSnapshot)

    if status_filter is not None:
        query = query.where(CommonCrawlSnapshot.status == status_filter.value)

    query = query.order_by(CommonCrawlSnapshot.created_at.desc()).limit(limit)

    result = await db.execute(query)
    snapshots = result.scalars().all()

    items = [
        SnapshotResponse(
            snapshot_id=snapshot.snapshot_id,
            status=snapshot.status,
            date_range_start=snapshot.date_range_start,
            date_range_end=snapshot.date_range_end,
            total_records=snapshot.total_records,
            edges_ingested=snapshot.edges_ingested,
            ingestion_started_at=snapshot.ingestion_started_at,
            ingestion_completed_at=snapshot.ingestion_completed_at,
            error_message=snapshot.error_message,
            notes=snapshot.notes,
            created_at=snapshot.created_at,
        )
        for snapshot in snapshots
    ]

    return SnapshotListResponse(items=items)


@router.post(
    "/snapshots",
    response_model=SnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register snapshot",
    description="Register a new Common Crawl snapshot for tracking and future ingestion.",
)
async def create_snapshot(
    request: CreateSnapshotRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> SnapshotResponse:
    """
    Register a new Common Crawl snapshot.

    Creates a new snapshot record with status='known'. The snapshot
    can then be ingested using the /commoncrawl/ingest endpoint.

    Args:
        request: Snapshot creation request with snapshot_id and optional metadata.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Created snapshot record.

    Raises:
        HTTPException: 409 if snapshot already exists.
    """
    # Check if snapshot already exists
    existing = await db.execute(
        select(CommonCrawlSnapshot).where(CommonCrawlSnapshot.snapshot_id == request.snapshot_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Snapshot '{request.snapshot_id}' already exists",
        )

    # Create new snapshot
    snapshot = CommonCrawlSnapshot(
        snapshot_id=request.snapshot_id,
        status=SnapshotStatus.KNOWN.value,
        date_range_start=request.date_range_start,
        date_range_end=request.date_range_end,
        notes=request.notes,
    )

    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)

    return SnapshotResponse(
        snapshot_id=snapshot.snapshot_id,
        status=snapshot.status,
        date_range_start=snapshot.date_range_start,
        date_range_end=snapshot.date_range_end,
        total_records=snapshot.total_records,
        edges_ingested=snapshot.edges_ingested,
        ingestion_started_at=snapshot.ingestion_started_at,
        ingestion_completed_at=snapshot.ingestion_completed_at,
        error_message=snapshot.error_message,
        notes=snapshot.notes,
        created_at=snapshot.created_at,
    )


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger ingestion",
    description="Trigger ingestion of a Common Crawl snapshot.",
)
async def trigger_ingest(
    request: IngestRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> IngestResponse:
    """
    Trigger ingestion for a Common Crawl snapshot.

    Validates the snapshot exists and is in an appropriate state,
    then updates the status to 'ingesting' and returns a 202 Accepted
    response. The actual ingestion is performed by background workers.

    Args:
        request: Ingestion request with snapshot_id and optional subset config.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Ingestion job info with snapshot_id and status.

    Raises:
        HTTPException: 404 if snapshot not found.
        HTTPException: 409 if snapshot is already ingesting or ingested.
    """
    # Fetch the snapshot
    result = await db.execute(
        select(CommonCrawlSnapshot).where(CommonCrawlSnapshot.snapshot_id == request.snapshot_id)
    )
    snapshot = result.scalar_one_or_none()

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot '{request.snapshot_id}' not found",
        )

    # Validate status allows ingestion
    if snapshot.status == SnapshotStatus.INGESTING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Snapshot '{request.snapshot_id}' is already being ingested (in progress)",
        )

    if snapshot.status == SnapshotStatus.INGESTED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Snapshot '{request.snapshot_id}' has already been fully ingested",
        )

    # Update status to ingesting
    snapshot.status = SnapshotStatus.INGESTING.value

    # Store subset config in spec if provided
    if request.subset is not None:
        subset_spec = {}
        if request.subset.target_domains:
            subset_spec["target_domains"] = request.subset.target_domains
        if request.subset.sample_rate is not None:
            subset_spec["sample_rate"] = request.subset.sample_rate
        if request.subset.max_edges is not None:
            subset_spec["max_edges"] = request.subset.max_edges
        if subset_spec:
            snapshot.spec = {**(snapshot.spec or {}), "subset": subset_spec}

    if request.build_aggregates:
        snapshot.spec = {**(snapshot.spec or {}), "build_aggregates": True}

    await db.commit()

    return IngestResponse(
        snapshot_id=snapshot.snapshot_id,
        status=SnapshotStatus.INGESTING.value,
        message="Ingestion started. Background workers will process the snapshot.",
    )


@router.get(
    "/snapshots/{snapshot_id}",
    response_model=SnapshotResponse,
    status_code=status.HTTP_200_OK,
    summary="Get snapshot details",
    description="Get detailed information about a specific snapshot.",
)
async def get_snapshot(
    snapshot_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> SnapshotResponse:
    """
    Get details for a specific Common Crawl snapshot.

    Returns full snapshot information including ingestion status,
    progress, and any error messages.

    Args:
        snapshot_id: Common Crawl snapshot identifier (e.g., 'CC-MAIN-2025-05').
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Snapshot details.

    Raises:
        HTTPException: 404 if snapshot not found.
    """
    result = await db.execute(
        select(CommonCrawlSnapshot).where(CommonCrawlSnapshot.snapshot_id == snapshot_id)
    )
    snapshot = result.scalar_one_or_none()

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot '{snapshot_id}' not found",
        )

    return SnapshotResponse(
        snapshot_id=snapshot.snapshot_id,
        status=snapshot.status,
        date_range_start=snapshot.date_range_start,
        date_range_end=snapshot.date_range_end,
        total_records=snapshot.total_records,
        edges_ingested=snapshot.edges_ingested,
        ingestion_started_at=snapshot.ingestion_started_at,
        ingestion_completed_at=snapshot.ingestion_completed_at,
        error_message=snapshot.error_message,
        notes=snapshot.notes,
        created_at=snapshot.created_at,
    )
