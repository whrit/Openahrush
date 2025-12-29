"""
Export Schedule endpoints for automated recurring exports.

Provides endpoints for:
- POST /projects/{project_id}/exports/schedules - Create schedule
- GET /projects/{project_id}/exports/schedules - List schedules
- GET /projects/{project_id}/exports/schedules/{schedule_id} - Get schedule
- PATCH /projects/{project_id}/exports/schedules/{schedule_id} - Update schedule
- DELETE /projects/{project_id}/exports/schedules/{schedule_id} - Delete schedule
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from semrush_core.models import ExportSchedule, Project
from sqlalchemy import func, select

from semrush_api.deps import CurrentUser, DbSession, Pagination
from semrush_api.schemas.schedule import (
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdate,
)
from semrush_api.services.schedule_service import (
    calculate_next_run,
    validate_cron_expression,
)

router = APIRouter(prefix="/projects/{project_id}/exports/schedules", tags=["Schedules"])


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


async def get_schedule_for_project(
    db: DbSession,
    project_id: UUID,
    schedule_id: UUID,
) -> ExportSchedule:
    """
    Get a schedule belonging to a project.

    Args:
        db: Database session.
        project_id: Project UUID.
        schedule_id: Schedule UUID.

    Returns:
        Schedule if found.

    Raises:
        HTTPException: 404 if schedule not found.
    """
    result = await db.execute(
        select(ExportSchedule).where(
            ExportSchedule.id == schedule_id,
            ExportSchedule.project_id == project_id,
        )
    )
    schedule = result.scalar_one_or_none()

    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    return schedule


@router.post(
    "",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create export schedule",
    description="Create a new recurring export schedule with cron expression.",
)
async def create_schedule(
    project_id: UUID,
    data: ScheduleCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ScheduleResponse:
    """
    Create a new export schedule.

    The schedule will automatically trigger exports based on the cron expression.

    Args:
        project_id: Project UUID.
        data: Schedule creation data.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Created schedule with calculated next_run_at.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Validate cron expression (already done in schema, but double-check)
    if not validate_cron_expression(data.cron_expression):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid cron expression: {data.cron_expression}",
        )

    # Calculate next run time
    next_run_at = calculate_next_run(data.cron_expression, data.timezone)

    # Create schedule record
    schedule = ExportSchedule(
        project_id=project_id,
        format=data.format.value,
        resource=data.resource.value,
        cron_expression=data.cron_expression,
        timezone=data.timezone,
        is_enabled=True,
        next_run_at=next_run_at,
        params=data.params or {},
    )

    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)

    return ScheduleResponse.from_model(schedule)


@router.get(
    "",
    response_model=ScheduleListResponse,
    status_code=status.HTTP_200_OK,
    summary="List export schedules",
    description="List all export schedules for a project with pagination.",
)
async def list_schedules(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    pagination: Pagination,
) -> ScheduleListResponse:
    """
    List all schedules for a project.

    Args:
        project_id: Project UUID.
        db: Database session.
        current_user: Current authenticated user.
        pagination: Pagination parameters.

    Returns:
        Paginated list of schedules.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Get total count
    count_result = await db.execute(
        select(func.count(ExportSchedule.id)).where(ExportSchedule.project_id == project_id)
    )
    total = count_result.scalar() or 0

    # Get paginated schedules
    result = await db.execute(
        select(ExportSchedule)
        .where(ExportSchedule.project_id == project_id)
        .order_by(ExportSchedule.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    schedules = result.scalars().all()

    return ScheduleListResponse(
        items=[ScheduleResponse.from_model(s) for s in schedules],
        total=total,
        page=pagination.page,
    )


@router.get(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get export schedule",
    description="Get details of a specific export schedule.",
    responses={
        404: {"description": "Schedule not found"},
    },
)
async def get_schedule(
    project_id: UUID,
    schedule_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ScheduleResponse:
    """
    Get a specific schedule.

    Args:
        project_id: Project UUID.
        schedule_id: Schedule UUID.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Schedule details.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Get schedule
    schedule = await get_schedule_for_project(db, project_id, schedule_id)

    return ScheduleResponse.from_model(schedule)


@router.patch(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update export schedule",
    description="Update an export schedule. Changes to cron_expression or timezone will recalculate next_run_at.",
    responses={
        404: {"description": "Schedule not found"},
        422: {"description": "Invalid cron expression"},
    },
)
async def update_schedule(
    project_id: UUID,
    schedule_id: UUID,
    data: ScheduleUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ScheduleResponse:
    """
    Update a schedule.

    If cron_expression, timezone, or is_enabled changes, next_run_at
    will be recalculated.

    Args:
        project_id: Project UUID.
        schedule_id: Schedule UUID.
        data: Schedule update data.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Updated schedule.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Get schedule
    schedule = await get_schedule_for_project(db, project_id, schedule_id)

    # Track if we need to recalculate next_run_at
    recalculate = False

    if data.cron_expression is not None:
        # Already validated in schema, but double-check
        if not validate_cron_expression(data.cron_expression):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid cron expression: {data.cron_expression}",
            )
        schedule.cron_expression = data.cron_expression
        recalculate = True

    if data.timezone is not None:
        schedule.timezone = data.timezone
        recalculate = True

    if data.is_enabled is not None:
        schedule.is_enabled = data.is_enabled
        recalculate = True

    if data.params is not None:
        schedule.params = data.params

    # Recalculate next_run_at if needed
    if recalculate:
        if schedule.is_enabled:
            schedule.next_run_at = calculate_next_run(
                schedule.cron_expression,
                schedule.timezone,
            )
        else:
            schedule.next_run_at = None

    await db.commit()
    await db.refresh(schedule)

    return ScheduleResponse.from_model(schedule)


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete export schedule",
    description="Delete an export schedule.",
    responses={
        404: {"description": "Schedule not found"},
    },
)
async def delete_schedule(
    project_id: UUID,
    schedule_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """
    Delete a schedule.

    Args:
        project_id: Project UUID.
        schedule_id: Schedule UUID.
        db: Database session.
        current_user: Current authenticated user.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Get schedule
    schedule = await get_schedule_for_project(db, project_id, schedule_id)

    await db.delete(schedule)
    await db.commit()
