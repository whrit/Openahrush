"""
Pydantic schemas for Common Crawl API resources.

Provides request/response validation for:
- Snapshot listing and details
- Snapshot registration
- Ingestion triggering
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class SnapshotResponse(BaseModel):
    """Response schema for a Common Crawl snapshot."""

    snapshot_id: str = Field(
        ..., description="Common Crawl snapshot identifier (e.g., CC-MAIN-2025-05)"
    )
    status: str = Field(..., description="Ingestion status: known, ingesting, ingested, or failed")
    date_range_start: date | None = Field(None, description="Start date of the crawl period")
    date_range_end: date | None = Field(None, description="End date of the crawl period")
    total_records: int | None = Field(
        None, ge=0, description="Total number of records in the snapshot"
    )
    edges_ingested: int | None = Field(None, ge=0, description="Number of edges ingested so far")
    ingestion_started_at: datetime | None = Field(None, description="When ingestion began")
    ingestion_completed_at: datetime | None = Field(None, description="When ingestion finished")
    error_message: str | None = Field(None, description="Error details if ingestion failed")
    notes: str | None = Field(None, description="Operator notes about the snapshot")
    created_at: datetime | None = Field(None, description="When the snapshot record was created")

    model_config = {"from_attributes": True}


class SnapshotListResponse(BaseModel):
    """Response schema for list of snapshots."""

    items: list[SnapshotResponse] = Field(..., description="List of snapshots")


class CreateSnapshotRequest(BaseModel):
    """Request schema for registering a new snapshot."""

    snapshot_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Common Crawl snapshot identifier (e.g., CC-MAIN-2025-05)",
    )
    date_range_start: date | None = Field(None, description="Start date of the crawl period")
    date_range_end: date | None = Field(None, description="End date of the crawl period")
    notes: str | None = Field(
        None, max_length=1000, description="Operator notes about the snapshot"
    )


class IngestSubset(BaseModel):
    """Subset configuration for targeted ingestion."""

    target_domains: list[str] | None = Field(
        None,
        description="Only ingest edges pointing to these target domains",
    )
    sample_rate: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Sample rate for ingestion (0.0-1.0, e.g., 0.1 = 10%)",
    )
    max_edges: int | None = Field(
        None,
        gt=0,
        description="Maximum number of edges to ingest",
    )


class IngestRequest(BaseModel):
    """Request schema for triggering snapshot ingestion."""

    snapshot_id: str = Field(
        ...,
        min_length=1,
        description="Common Crawl snapshot identifier to ingest",
    )
    subset: IngestSubset | None = Field(
        None,
        description="Subset configuration for targeted ingestion",
    )
    build_aggregates: bool = Field(
        default=False,
        description="Whether to build aggregate tables after ingestion",
    )


class IngestResponse(BaseModel):
    """Response schema for ingestion trigger (202 Accepted)."""

    snapshot_id: str = Field(..., description="Snapshot being ingested")
    status: str = Field(..., description="Current status (should be 'ingesting')")
    message: str = Field(
        default="Ingestion started",
        description="Status message",
    )
