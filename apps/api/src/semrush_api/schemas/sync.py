"""
Pydantic schemas for sync status, data freshness, and integration health.

Provides request/response validation for:
- Sync status monitoring
- Data freshness tracking
- Integration health checks
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SyncStatusResponse(BaseModel):
    """Response schema for sync status of a mapping."""

    mapping_id: UUID = Field(..., description="Integration mapping UUID")
    provider: str = Field(..., description="Provider name (e.g., google_search_console)")
    property_id: str | None = Field(None, description="External property identifier")
    status: str = Field(
        ...,
        description="Current sync status (never, queued, running, completed, failed)",
    )
    last_sync_at: datetime | None = Field(
        None, description="Timestamp of last completed sync"
    )
    next_sync_at: datetime | None = Field(
        None, description="Estimated next sync time"
    )
    error_count: int = Field(0, description="Number of consecutive sync failures")
    error_message: str | None = Field(
        None, description="Most recent error message if sync failed"
    )
    is_healthy: bool = Field(
        ...,
        description="Whether sync is healthy (recent and no consecutive failures)",
    )
    status_message: str = Field(
        ..., description="Human-readable status description"
    )

    model_config = {"from_attributes": True}


class DataFreshnessResponse(BaseModel):
    """Response schema for data freshness metrics."""

    mapping_id: UUID = Field(..., description="Integration mapping UUID")
    provider: str = Field(..., description="Provider name")
    property_id: str | None = Field(None, description="External property identifier")
    latest_data_date: date | None = Field(
        None, description="Most recent date with data"
    )
    expected_lag_days: int = Field(
        ..., description="Expected data lag for this provider in days"
    )
    days_behind: int = Field(
        0, description="Days behind expected freshness (0 = on target)"
    )
    coverage_pct: float = Field(
        0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of expected dates with data",
    )
    is_fresh: bool = Field(
        ..., description="Whether data is within acceptable freshness threshold"
    )
    status_message: str = Field(
        ..., description="Human-readable freshness description"
    )

    model_config = {"from_attributes": True}


class IntegrationHealthResponse(BaseModel):
    """Response schema for overall integration health."""

    provider: str = Field(..., description="Provider name")
    connected: bool = Field(..., description="Whether integration account exists")
    token_valid: bool = Field(
        ..., description="Whether OAuth token is valid and not expired"
    )
    properties_count: int = Field(
        0, description="Number of discovered properties"
    )
    last_sync: datetime | None = Field(
        None, description="Most recent sync across all properties"
    )
    is_healthy: bool = Field(
        ..., description="Overall health status of the integration"
    )
    status_message: str = Field(
        ..., description="Human-readable health description"
    )

    model_config = {"from_attributes": True}


class ProjectSyncStatusResponse(BaseModel):
    """Response schema for all sync statuses in a project."""

    project_id: UUID
    mappings: list[SyncStatusResponse]
    overall_healthy: bool = Field(
        ..., description="Whether all syncs are healthy"
    )

    model_config = {"from_attributes": True}


class ProjectDataFreshnessResponse(BaseModel):
    """Response schema for all data freshness in a project."""

    project_id: UUID
    mappings: list[DataFreshnessResponse]
    overall_fresh: bool = Field(
        ..., description="Whether all data is fresh"
    )

    model_config = {"from_attributes": True}


class TriggerSyncRequest(BaseModel):
    """Request schema for triggering a manual sync."""

    mode: str = Field(
        "incremental",
        description="Sync mode (incremental or backfill)",
        pattern="^(incremental|backfill)$",
    )
    date_range_start: date | None = Field(
        None, description="Start date for backfill (optional)"
    )
    date_range_end: date | None = Field(
        None, description="End date for backfill (optional)"
    )


class TriggerSyncResponse(BaseModel):
    """Response schema for triggered sync."""

    sync_run_id: UUID = Field(..., description="ID of the created sync run")
    mapping_id: UUID = Field(..., description="Integration mapping ID")
    status: str = Field(..., description="Initial sync status (typically 'queued')")
    message: str = Field(..., description="Confirmation message")

    model_config = {"from_attributes": True}
