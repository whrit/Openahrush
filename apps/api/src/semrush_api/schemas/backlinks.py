"""
Pydantic schemas for Backlinks API resources.

Provides request/response validation for:
- Domain explorer (referring domains, backlinks, anchors)
- New/lost domain detection
- Competitive analysis (overlap, intersect)
- Project backlinks management
"""

from datetime import date as date_type
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RefDomainResponse(BaseModel):
    """Response schema for a referring domain."""

    ref_domain: str = Field(..., description="Referring domain name")
    backlinks: int = Field(..., ge=0, description="Number of backlinks from this domain")
    first_seen: datetime | None = Field(None, description="When first discovered")
    last_seen: datetime | None = Field(None, description="Most recent observation")

    model_config = {"from_attributes": True}


class RefDomainListResponse(BaseModel):
    """Response schema for list of referring domains."""

    items: list[RefDomainResponse] = Field(..., description="List of referring domains")


class BacklinkResponse(BaseModel):
    """Response schema for an individual backlink."""

    source_url: str = Field(..., description="Full URL of the linking page")
    source_domain: str = Field(..., description="Domain of the source page")
    target_url: str = Field(..., description="URL being linked to")
    target_domain: str = Field(..., description="Domain of the target page")
    anchor: str | None = Field(None, description="Link anchor text")
    flags: dict[str, bool] = Field(
        default_factory=dict,
        description="Link flags (dofollow, image, etc.)",
    )

    model_config = {"from_attributes": True}


class BacklinkListResponse(BaseModel):
    """Response schema for paginated list of backlinks."""

    items: list[BacklinkResponse] = Field(..., description="List of backlinks")
    total: int = Field(..., ge=0, description="Total number of backlinks")
    limit: int = Field(..., ge=1, description="Items per page")
    offset: int = Field(..., ge=0, description="Offset from start")


class AnchorResponse(BaseModel):
    """Response schema for anchor text with count."""

    anchor: str = Field(..., description="Anchor text")
    count: int = Field(..., ge=0, description="Number of occurrences")

    model_config = {"from_attributes": True}


class AnchorListResponse(BaseModel):
    """Response schema for list of anchors."""

    items: list[AnchorResponse] = Field(..., description="List of anchors with counts")


class NewLostResponse(BaseModel):
    """Response schema for new/lost referring domains comparison."""

    new: list[RefDomainResponse] = Field(
        default_factory=list,
        description="Referring domains in snapshot_b but not in snapshot_a",
    )
    lost: list[RefDomainResponse] = Field(
        default_factory=list,
        description="Referring domains in snapshot_a but not in snapshot_b",
    )


class SharedRefDomain(BaseModel):
    """A referring domain that links to multiple domains."""

    ref_domain: str = Field(..., description="Referring domain name")
    domains_linking_to: list[str] = Field(
        ...,
        description="List of domains this ref domain links to",
    )
    backlinks: int = Field(default=0, ge=0, description="Total backlink count")


class OverlapResponse(BaseModel):
    """Response schema for domain overlap analysis."""

    domain: str = Field(..., description="Primary domain being analyzed")
    competitors: list[str] = Field(..., description="Competitor domains compared")
    shared_ref_domains: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Referring domains linking to both primary and at least one competitor",
    )


class IntersectRefDomain(BaseModel):
    """A referring domain that links to competitors but not the primary domain."""

    ref_domain: str = Field(..., description="Referring domain name")
    links_to_competitors: list[str] = Field(
        ...,
        description="List of competitor domains this ref domain links to",
    )
    backlinks: int = Field(default=0, ge=0, description="Total backlink count")


class IntersectResponse(BaseModel):
    """Response schema for domain intersect analysis (link building opportunities)."""

    domain: str = Field(..., description="Primary domain being analyzed")
    competitors: list[str] = Field(..., description="Competitor domains compared")
    intersect_ref_domains: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Referring domains linking to competitors but NOT to primary domain",
    )


class ImportResponse(BaseModel):
    """Response schema for CSV import operation."""

    imported: int = Field(..., ge=0, description="Number of successfully imported rows")
    errors: int = Field(..., ge=0, description="Number of rows with errors")
    error_details: list[str] = Field(
        default_factory=list,
        description="Details of errors encountered",
    )


class BacklinkOverviewResponse(BaseModel):
    """Response schema for project backlink overview."""

    total_backlinks: int = Field(..., ge=0, description="Total number of backlinks")
    unique_ref_domains: int = Field(
        ...,
        ge=0,
        description="Number of unique referring domains",
    )
    dofollow_count: int = Field(default=0, ge=0, description="Number of dofollow links")
    nofollow_count: int = Field(default=0, ge=0, description="Number of nofollow links")
    first_seen: datetime | None = Field(
        None,
        description="Earliest backlink discovery date",
    )
    last_seen: datetime | None = Field(
        None,
        description="Most recent backlink discovery date",
    )

    model_config = {"from_attributes": True}


# =============================================================================
# Time Series Schemas (Sprint 3)
# =============================================================================


class NewLostSeriesItem(BaseModel):
    """Single time series data point for new/lost domain tracking."""

    snapshot_id: UUID = Field(..., description="Snapshot ID for this data point")
    date: date_type = Field(..., description="Date of the snapshot")
    new_count: int = Field(..., ge=0, description="Number of new referring domains")
    lost_count: int = Field(..., ge=0, description="Number of lost referring domains")

    model_config = {"from_attributes": True}


class NewLostSeriesResponse(BaseModel):
    """Response schema for new/lost time series across multiple snapshots."""

    domain: str = Field(..., description="Target domain being analyzed")
    items: list[NewLostSeriesItem] = Field(
        default_factory=list,
        description="Time series data points ordered by date descending",
    )


class ProjectNewLostItem(BaseModel):
    """Single time series data point for project new/lost backlinks."""

    date: date_type = Field(..., description="Date for this data point")
    new_count: int = Field(..., ge=0, description="Number of new backlinks discovered")
    lost_count: int = Field(..., ge=0, description="Number of lost backlinks")

    model_config = {"from_attributes": True}


class ProjectNewLostResponse(BaseModel):
    """Response schema for project backlink new/lost time series."""

    project_id: UUID = Field(..., description="Project ID")
    items: list[ProjectNewLostItem] = Field(
        default_factory=list,
        description="Time series data points ordered by date descending",
    )


# =============================================================================
# Project Competitive Analysis Schemas (Sprint 3)
# =============================================================================


class ProjectOverlapResponse(BaseModel):
    """Response schema for project overlap analysis using project's competitors."""

    project_id: UUID = Field(..., description="Project ID")
    domain: str = Field(..., description="Primary domain from project's site")
    competitors: list[str] = Field(..., description="Competitor domains from project")
    shared_ref_domains: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Referring domains linking to both primary and at least one competitor",
    )


class ProjectIntersectResponse(BaseModel):
    """Response schema for project intersect analysis (link building opportunities)."""

    project_id: UUID = Field(..., description="Project ID")
    domain: str = Field(..., description="Primary domain from project's site")
    competitors: list[str] = Field(..., description="Competitor domains from project")
    intersect_ref_domains: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Referring domains linking to competitors but NOT to primary domain",
    )
