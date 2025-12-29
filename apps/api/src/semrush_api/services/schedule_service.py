"""
Schedule service for managing export schedules.

Provides business logic for:
- Creating export schedules with cron validation
- Retrieving and listing schedules
- Updating schedules and recalculating next_run_at
- Deleting schedules
"""

from __future__ import annotations

import uuid
import zoneinfo
from datetime import UTC, datetime
from typing import Any

from croniter import croniter
from semrush_core.models import ExportFormat, ExportResource, ExportSchedule
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def validate_cron_expression(cron_expression: str) -> bool:
    """
    Validate a cron expression.

    Args:
        cron_expression: The cron expression to validate.

    Returns:
        True if valid, False otherwise.
    """
    return croniter.is_valid(cron_expression)


def calculate_next_run(
    cron_expression: str,
    timezone: str = "UTC",
    base_time: datetime | None = None,
) -> datetime:
    """
    Calculate the next run time for a cron expression.

    Args:
        cron_expression: The cron expression.
        timezone: The timezone for evaluation.
        base_time: The base time to calculate from (defaults to now).

    Returns:
        The next run time as a UTC datetime.

    Raises:
        ValueError: If the cron expression is invalid.
    """
    if not validate_cron_expression(cron_expression):
        raise ValueError(f"Invalid cron expression: {cron_expression}")

    # Get the timezone
    try:
        tz = zoneinfo.ZoneInfo(timezone)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")

    # Use base_time or current time in the specified timezone
    if base_time is None:
        base_time = datetime.now(tz)
    elif base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=tz)
    else:
        base_time = base_time.astimezone(tz)

    # Calculate next run
    cron = croniter(cron_expression, base_time)
    next_run = cron.get_next(datetime)

    # Convert to UTC
    if next_run.tzinfo is None:
        next_run = next_run.replace(tzinfo=tz)

    return next_run.astimezone(UTC)


class ScheduleService:
    """
    Service for managing export schedule operations.

    Handles all schedule-related business logic including creation,
    retrieval, listing, updates, and deletion.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the schedule service.

        Args:
            db: Async database session.
        """
        self.db = db

    async def create_schedule(
        self,
        project_id: uuid.UUID,
        format: ExportFormat,
        resource: ExportResource,
        cron_expression: str,
        timezone: str = "UTC",
        params: dict[str, Any] | None = None,
    ) -> ExportSchedule:
        """
        Create a new export schedule.

        Creates a schedule record with calculated next_run_at based on
        the cron expression and timezone.

        Args:
            project_id: UUID of the parent project.
            format: Export format (csv, json, pdf).
            resource: Resource to export (issues, backlinks, etc.).
            cron_expression: Cron expression for scheduling.
            timezone: Timezone for cron evaluation.
            params: Optional filter/date range parameters.

        Returns:
            Created schedule record.

        Raises:
            ValueError: If the cron expression is invalid.
        """
        # Validate and calculate next run
        if not validate_cron_expression(cron_expression):
            raise ValueError(f"Invalid cron expression: {cron_expression}")

        next_run_at = calculate_next_run(cron_expression, timezone)

        schedule = ExportSchedule(
            project_id=project_id,
            format=format.value,
            resource=resource.value,
            cron_expression=cron_expression,
            timezone=timezone,
            is_enabled=True,
            next_run_at=next_run_at,
            params=params or {},
        )

        self.db.add(schedule)
        await self.db.commit()
        await self.db.refresh(schedule)

        return schedule

    async def get_schedule(
        self,
        schedule_id: uuid.UUID,
        project_id: uuid.UUID | None = None,
    ) -> ExportSchedule | None:
        """
        Get a schedule by ID.

        Args:
            schedule_id: Schedule UUID.
            project_id: Optional project UUID for validation.

        Returns:
            Schedule if found, None otherwise.
        """
        query = select(ExportSchedule).where(ExportSchedule.id == schedule_id)

        if project_id is not None:
            query = query.where(ExportSchedule.project_id == project_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_schedules(
        self,
        project_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ExportSchedule], int]:
        """
        List schedules for a project with pagination.

        Args:
            project_id: Project UUID.
            limit: Maximum number of schedules to return.
            offset: Number of schedules to skip.

        Returns:
            Tuple of (list of schedules, total count).
        """
        # Get total count
        count_query = select(func.count(ExportSchedule.id)).where(
            ExportSchedule.project_id == project_id
        )
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated schedules
        schedules_query = (
            select(ExportSchedule)
            .where(ExportSchedule.project_id == project_id)
            .order_by(ExportSchedule.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(schedules_query)
        schedules = list(result.scalars().all())

        return schedules, total

    async def update_schedule(
        self,
        schedule_id: uuid.UUID,
        project_id: uuid.UUID,
        cron_expression: str | None = None,
        timezone: str | None = None,
        is_enabled: bool | None = None,
        params: dict[str, Any] | None = None,
    ) -> ExportSchedule | None:
        """
        Update a schedule.

        Updates the schedule fields and recalculates next_run_at
        if cron_expression, timezone, or is_enabled changes.

        Args:
            schedule_id: Schedule UUID.
            project_id: Project UUID for validation.
            cron_expression: New cron expression (optional).
            timezone: New timezone (optional).
            is_enabled: New enabled state (optional).
            params: New parameters (optional).

        Returns:
            Updated schedule if found, None otherwise.

        Raises:
            ValueError: If the new cron expression is invalid.
        """
        schedule = await self.get_schedule(schedule_id, project_id)
        if schedule is None:
            return None

        # Track if we need to recalculate next_run_at
        recalculate = False

        if cron_expression is not None:
            if not validate_cron_expression(cron_expression):
                raise ValueError(f"Invalid cron expression: {cron_expression}")
            schedule.cron_expression = cron_expression
            recalculate = True

        if timezone is not None:
            schedule.timezone = timezone
            recalculate = True

        if is_enabled is not None:
            schedule.is_enabled = is_enabled
            recalculate = True

        if params is not None:
            schedule.params = params

        # Recalculate next_run_at if needed
        if recalculate:
            if schedule.is_enabled:
                schedule.next_run_at = calculate_next_run(
                    schedule.cron_expression,
                    schedule.timezone,
                )
            else:
                schedule.next_run_at = None

        await self.db.commit()
        await self.db.refresh(schedule)

        return schedule

    async def delete_schedule(
        self,
        schedule_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> bool:
        """
        Delete a schedule.

        Args:
            schedule_id: Schedule UUID.
            project_id: Project UUID for validation.

        Returns:
            True if schedule was deleted, False if not found.
        """
        schedule = await self.get_schedule(schedule_id, project_id)
        if schedule is None:
            return False

        await self.db.delete(schedule)
        await self.db.commit()

        return True

    async def mark_schedule_run(
        self,
        schedule_id: uuid.UUID,
    ) -> ExportSchedule | None:
        """
        Mark a schedule as having been run.

        Updates last_run_at and recalculates next_run_at.

        Args:
            schedule_id: Schedule UUID.

        Returns:
            Updated schedule if found, None otherwise.
        """
        schedule = await self.get_schedule(schedule_id)
        if schedule is None:
            return None

        schedule.last_run_at = datetime.now(UTC)

        if schedule.is_enabled:
            schedule.next_run_at = calculate_next_run(
                schedule.cron_expression,
                schedule.timezone,
            )
        else:
            schedule.next_run_at = None

        await self.db.commit()
        await self.db.refresh(schedule)

        return schedule

    async def get_due_schedules(self) -> list[ExportSchedule]:
        """
        Get all schedules that are due to run.

        Returns schedules where:
        - is_enabled is True
        - next_run_at is not None
        - next_run_at <= now

        Returns:
            List of schedules that are due.
        """
        now = datetime.now(UTC)

        query = (
            select(ExportSchedule)
            .where(
                ExportSchedule.is_enabled.is_(True),
                ExportSchedule.next_run_at.is_not(None),
                ExportSchedule.next_run_at <= now,
            )
            .order_by(ExportSchedule.next_run_at.asc())
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())
