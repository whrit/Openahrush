"""
Pydantic schemas for Project, Site, and Competitor resources.

Provides request/response validation for:
- Project CRUD operations
- Site management within projects
- Competitor tracking within projects
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Request schema for creating a new project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")


class ProjectUpdate(BaseModel):
    """Request schema for updating an existing project."""

    name: str | None = Field(
        None, min_length=1, max_length=255, description="Updated project name"
    )


class ProjectResponse(BaseModel):
    """Response schema for a single project."""

    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectList(BaseModel):
    """Response schema for paginated list of projects."""

    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int


class SiteCreate(BaseModel):
    """Request schema for adding a site to a project."""

    domain: str = Field(..., min_length=1, description="Domain name (e.g., example.com)")
    base_url: str = Field(
        ...,
        pattern=r"^https?://",
        description="Base URL (must start with http:// or https://)",
    )


class SiteResponse(BaseModel):
    """Response schema for a site."""

    id: UUID
    project_id: UUID
    domain: str
    base_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SiteList(BaseModel):
    """Response schema for list of sites."""

    items: list[SiteResponse]


class CompetitorCreate(BaseModel):
    """Request schema for adding a competitor to a project."""

    domain: str = Field(..., min_length=1, description="Competitor domain name")


class CompetitorResponse(BaseModel):
    """Response schema for a competitor."""

    id: UUID
    project_id: UUID
    domain: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CompetitorList(BaseModel):
    """Response schema for list of competitors."""

    items: list[CompetitorResponse]
