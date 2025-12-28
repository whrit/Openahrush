"""
Project settings API router.

Provides endpoints for managing project-level configuration:
- GET /projects/{project_id}/settings - Retrieve settings with defaults
- PUT /projects/{project_id}/settings - Update settings

Settings are stored as JSONB in the project_settings table and merged
with defaults when retrieved.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from semrush_core.database import get_async_session
from semrush_core.models import Project, ProjectSettings
from semrush_core.security.jwt import TokenData

from semrush_api.deps import get_current_user
from semrush_api.schemas.settings import (
    DEFAULT_SETTINGS,
    ProjectSettingsSchema,
    SettingsUpdateResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings"])


async def _get_project_or_404(
    project_id: UUID,
    db: AsyncSession,
    current_user: TokenData,
) -> Project:
    """
    Get project by ID or raise 404.

    Validates that:
    1. Project exists
    2. Current user owns the project

    Args:
        project_id: UUID of the project to find.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Project if found and owned by user.

    Raises:
        HTTPException: 404 if project not found or not owned by user.
    """
    query = select(Project).where(Project.id == project_id)
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Check ownership
    if str(project.owner_id) != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project


async def _get_settings_record(
    project_id: UUID,
    db: AsyncSession,
) -> ProjectSettings | None:
    """
    Get existing settings record for a project.

    Args:
        project_id: UUID of the project.
        db: Database session.

    Returns:
        ProjectSettings if exists, None otherwise.
    """
    query = select(ProjectSettings).where(ProjectSettings.project_id == project_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


def _merge_with_defaults(saved_settings: dict[str, Any]) -> dict[str, Any]:
    """
    Merge saved settings with defaults.

    Saved values take precedence over defaults.

    Args:
        saved_settings: Settings stored in database.

    Returns:
        Complete settings dict with all fields.
    """
    return {**DEFAULT_SETTINGS, **saved_settings}


@router.get(
    "/projects/{project_id}/settings",
    response_model=ProjectSettingsSchema,
    summary="Get project settings",
    description=(
        "Retrieve settings for a project. Returns default values for any "
        "settings that have not been explicitly configured."
    ),
)
async def get_settings(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: TokenData = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get project settings.

    Returns the current settings for the project, merged with defaults
    for any fields that have not been explicitly set.

    Args:
        project_id: UUID of the project.
        db: Database session (injected).
        current_user: Current authenticated user (injected).

    Returns:
        Complete project settings with defaults applied.

    Raises:
        HTTPException: 401 if not authenticated, 404 if project not found.
    """
    # Validate project exists and user has access
    await _get_project_or_404(project_id, db, current_user)

    # Get existing settings or use empty dict
    settings_record = await _get_settings_record(project_id, db)

    if settings_record is None:
        # No settings saved yet, return all defaults
        logger.debug("No settings found for project %s, returning defaults", project_id)
        return DEFAULT_SETTINGS

    # Merge saved settings with defaults
    merged = _merge_with_defaults(settings_record.settings)
    logger.debug("Returning merged settings for project %s", project_id)

    return merged


@router.put(
    "/projects/{project_id}/settings",
    response_model=SettingsUpdateResponse,
    summary="Update project settings",
    description=(
        "Update settings for a project. All provided fields will be saved. "
        "Fields not provided will use default values on retrieval."
    ),
)
async def update_settings(
    project_id: UUID,
    data: ProjectSettingsSchema,
    db: AsyncSession = Depends(get_async_session),
    current_user: TokenData = Depends(get_current_user),
) -> SettingsUpdateResponse:
    """
    Update project settings.

    Replaces the entire settings object with the provided values.
    Use GET first if you need to preserve existing values.

    Args:
        project_id: UUID of the project.
        data: New settings values (validated by Pydantic).
        db: Database session (injected).
        current_user: Current authenticated user (injected).

    Returns:
        Success response with ok=True.

    Raises:
        HTTPException: 401 if not authenticated, 404 if project not found,
                      422 if validation fails.
    """
    # Validate project exists and user has access
    project = await _get_project_or_404(project_id, db, current_user)

    # Get existing settings record or create new one
    settings_record = await _get_settings_record(project_id, db)

    if settings_record is None:
        # Create new settings record
        settings_record = ProjectSettings(
            project_id=project_id,
            settings=data.model_dump(),
        )
        db.add(settings_record)
        logger.info("Created new settings for project %s", project_id)
    else:
        # Update existing settings
        settings_record.settings = data.model_dump()
        logger.info("Updated settings for project %s", project_id)

    await db.commit()

    return SettingsUpdateResponse()
