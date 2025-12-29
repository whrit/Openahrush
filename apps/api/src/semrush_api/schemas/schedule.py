"""
Pydantic schemas for export schedule endpoints.

Provides request/response validation for:
- Schedule creation and updates
- Schedule listing with pagination
- Cron expression validation
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator
from semrush_core.models.export import ExportFormat, ExportResource


class ScheduleCreate(BaseModel):
    """Request schema for creating a new export schedule."""

    format: ExportFormat = Field(
        ...,
        description="Export format (csv, json, pdf)",
    )
    resource: ExportResource = Field(
        ...,
        description="Resource to export (issues, backlinks, pages, performance, full_report)",
    )
    cron_expression: str = Field(
        ...,
        description="Cron expression for scheduling (e.g., '0 9 * * MON' for every Monday at 9:00)",
        min_length=5,
        max_length=100,
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for cron evaluation (e.g., 'America/New_York', 'Europe/London')",
        max_length=64,
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description="Export parameters (filters, date ranges, etc.)",
    )

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        """Validate the cron expression format."""
        from croniter import croniter

        v = v.strip()
        if not v:
            raise ValueError("Cron expression cannot be empty")

        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v}")

        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate the timezone string."""
        import zoneinfo

        v = v.strip()
        if not v:
            return "UTC"

        try:
            zoneinfo.ZoneInfo(v)
        except Exception as e:
            raise ValueError(f"Invalid timezone: {v}") from e

        return v


class ScheduleUpdate(BaseModel):
    """Request schema for updating an export schedule."""

    cron_expression: str | None = Field(
        default=None,
        description="New cron expression for scheduling",
        min_length=5,
        max_length=100,
    )
    timezone: str | None = Field(
        default=None,
        description="New timezone for cron evaluation",
        max_length=64,
    )
    is_enabled: bool | None = Field(
        default=None,
        description="Enable or disable the schedule",
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description="Updated export parameters",
    )

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        """Validate the cron expression format if provided."""
        if v is None:
            return None

        from croniter import croniter

        v = v.strip()
        if not v:
            raise ValueError("Cron expression cannot be empty")

        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v}")

        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        """Validate the timezone string if provided."""
        if v is None:
            return None

        import zoneinfo

        v = v.strip()
        if not v:
            return None

        try:
            zoneinfo.ZoneInfo(v)
        except Exception as e:
            raise ValueError(f"Invalid timezone: {v}") from e

        return v


class ScheduleResponse(BaseModel):
    """Response schema for a single export schedule."""

    id: str
    format: str
    resource: str
    cron_expression: str
    timezone: str
    is_enabled: bool
    params: dict[str, Any] | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, schedule: Any) -> "ScheduleResponse":
        """Create response from SQLAlchemy model."""
        return cls(
            id=str(schedule.id),
            format=schedule.format,
            resource=schedule.resource,
            cron_expression=schedule.cron_expression,
            timezone=schedule.timezone,
            is_enabled=schedule.is_enabled,
            params=schedule.params,
            last_run_at=schedule.last_run_at,
            next_run_at=schedule.next_run_at,
            created_at=schedule.created_at,
        )


class ScheduleListResponse(BaseModel):
    """Response schema for paginated list of schedules."""

    items: list[ScheduleResponse]
    total: int
    page: int
