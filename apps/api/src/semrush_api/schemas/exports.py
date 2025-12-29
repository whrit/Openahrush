"""
Pydantic schemas for export endpoints.

Provides request/response validation for:
- Export creation and listing
- Export status and download
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from semrush_core.models.export import ExportFormat, ExportResource, ExportStatus


class ExportCreate(BaseModel):
    """Request schema for creating a new export."""

    format: ExportFormat = Field(
        ...,
        description="Export format (csv, json, pdf)",
    )
    resource: ExportResource = Field(
        ...,
        description="Resource to export (issues, backlinks, pages, performance, full_report)",
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description="Export parameters (filters, date ranges, etc.)",
    )


class ExportResponse(BaseModel):
    """Response schema for a single export."""

    id: UUID
    project_id: UUID
    format: str
    resource: str
    status: str
    params: dict[str, Any] | None = None
    artifact_key: str | None = None
    file_size_bytes: int | None = None
    download_url: str | None = None
    download_expires_at: datetime | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExportList(BaseModel):
    """Response schema for paginated list of exports."""

    items: list[ExportResponse]
    total: int
    page: int
    page_size: int


class ExportDownload(BaseModel):
    """Response schema for export download URL."""

    export_id: UUID
    download_url: str
    expires_at: datetime
    file_size_bytes: int | None = None
    content_type: str


class ExportStatusResponse(BaseModel):
    """Response schema for export status check."""

    id: UUID
    status: str
    progress: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Export progress percentage",
    )
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    download_url: str | None = None


# Parameter schemas for different export types

class IssuesExportParams(BaseModel):
    """Parameters for issues export."""

    crawl_run_id: UUID | None = Field(
        default=None,
        description="Filter by specific crawl run",
    )
    severity_min: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Minimum severity level (1-5)",
    )
    category: str | None = Field(
        default=None,
        description="Filter by issue category",
    )


class BacklinksExportParams(BaseModel):
    """Parameters for backlinks export."""

    source_type: str | None = Field(
        default=None,
        description="Filter by source type (import, crawl, commoncrawl, provider)",
    )
    source_domain: str | None = Field(
        default=None,
        description="Filter by source domain (partial match)",
    )


class PagesExportParams(BaseModel):
    """Parameters for pages export."""

    crawl_run_id: UUID = Field(
        ...,
        description="Crawl run ID (required)",
    )
    status_code: int | None = Field(
        default=None,
        ge=100,
        le=599,
        description="Filter by HTTP status code",
    )


class PerformanceExportParams(BaseModel):
    """Parameters for performance data export."""

    date_start: datetime | None = Field(
        default=None,
        description="Start date for data range",
    )
    date_end: datetime | None = Field(
        default=None,
        description="End date for data range",
    )
    aggregation: str = Field(
        default="daily",
        pattern="^(daily|weekly|monthly)$",
        description="Aggregation level",
    )
