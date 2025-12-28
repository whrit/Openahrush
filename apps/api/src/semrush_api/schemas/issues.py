"""
Pydantic schemas for Issue resources.

Provides request/response validation for:
- Issue listing with pagination
- Issue filtering and sorting
- Issue details with evidence
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IssueSeverityEnum(int, Enum):
    """Issue severity levels."""

    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


class IssueSortField(str, Enum):
    """Fields available for sorting issues."""

    IMPACT_SCORE = "impact_score"
    SEVERITY = "severity"
    CATEGORY = "category"
    CREATED_AT = "created_at"


class IssueTypeResponse(BaseModel):
    """Response schema for an issue type."""

    id: str = Field(..., description="Issue type identifier")
    category: str = Field(..., description="Issue category")
    severity: int = Field(..., ge=1, le=5, description="Severity level (1-5)")
    name: str = Field(..., description="Human-readable name")
    description: str | None = Field(None, description="Description of the issue")
    recommendation: str | None = Field(None, description="How to fix the issue")

    model_config = {"from_attributes": True}


class IssueInstanceResponse(BaseModel):
    """Response schema for a single issue instance."""

    id: UUID = Field(..., description="Issue instance ID")
    crawl_run_id: UUID = Field(..., description="ID of the crawl run")
    crawl_page_id: UUID | None = Field(None, description="ID of the affected page")
    issue_type_id: str = Field(..., description="Issue type identifier")
    affected_url: str = Field(..., description="URL where issue was detected")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    impact_score: float | None = Field(None, description="Computed impact score")
    severity: int = Field(..., ge=1, le=5, description="Severity level")
    evidence: dict[str, Any] = Field(default_factory=dict, description="Issue evidence")
    created_at: datetime = Field(..., description="When the issue was detected")

    # Optional expanded issue type info
    issue_type: IssueTypeResponse | None = Field(
        None, description="Issue type details (when expanded)"
    )

    model_config = {"from_attributes": True}


class IssueListResponse(BaseModel):
    """Response schema for paginated list of issues."""

    items: list[IssueInstanceResponse] = Field(..., description="List of issues")
    total: int = Field(..., ge=0, description="Total number of issues")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")


class IssueFilterParams(BaseModel):
    """Query parameters for filtering issues."""

    issue_type_id: str | None = Field(
        None, description="Filter by issue type ID", alias="issueTypeId"
    )
    severity: int | None = Field(
        None, ge=1, le=5, description="Filter by severity level"
    )
    min_impact_score: float | None = Field(
        None, ge=0.0, description="Minimum impact score", alias="minImpactScore"
    )
    affected_url: str | None = Field(
        None, description="Filter by URL (partial match)", alias="affectedUrl"
    )

    model_config = {"populate_by_name": True}


class IssueSummary(BaseModel):
    """Summary of issues by severity/category."""

    total_issues: int = Field(..., description="Total issue count")
    by_severity: dict[str, int] = Field(
        default_factory=dict, description="Count by severity"
    )
    by_category: dict[str, int] = Field(
        default_factory=dict, description="Count by category"
    )
    top_issues: list[IssueInstanceResponse] = Field(
        default_factory=list, description="Top issues by impact"
    )
