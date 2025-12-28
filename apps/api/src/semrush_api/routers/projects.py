"""
Projects CRUD endpoints.

Provides endpoints for:
- GET /projects - List user's projects (paginated)
- POST /projects - Create a new project
- GET /projects/{project_id} - Get a specific project
- PATCH /projects/{project_id} - Update a project
- DELETE /projects/{project_id} - Delete a project
- POST /projects/{project_id}/sites - Add a site to a project
- POST /projects/{project_id}/competitors - Add a competitor to a project
- GET /projects/{project_id}/competitors - List project competitors
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from semrush_api.deps import CurrentUser, DbSession, Pagination
from semrush_api.schemas.project import (
    CompetitorCreate,
    CompetitorList,
    CompetitorResponse,
    ProjectCreate,
    ProjectList,
    ProjectResponse,
    ProjectUpdate,
    SiteCreate,
    SiteResponse,
)
from semrush_core.models import Competitor, Project, Site

router = APIRouter(prefix="/projects", tags=["Projects"])


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


@router.get(
    "",
    response_model=ProjectList,
    status_code=status.HTTP_200_OK,
    summary="List projects",
    description="List all projects owned by the authenticated user with pagination.",
)
async def list_projects(
    db: DbSession,
    current_user: CurrentUser,
    pagination: Pagination,
) -> ProjectList:
    """
    List all projects owned by the current user.

    Args:
        db: Database session.
        current_user: Current authenticated user.
        pagination: Pagination parameters.

    Returns:
        Paginated list of projects.
    """
    # Get total count
    count_result = await db.execute(
        select(func.count(Project.id)).where(Project.owner_id == current_user.user_id)
    )
    total = count_result.scalar() or 0

    # Get paginated projects
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == current_user.user_id)
        .order_by(Project.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    projects = result.scalars().all()

    return ProjectList(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
    description="Create a new project for the authenticated user.",
)
async def create_project(
    data: ProjectCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectResponse:
    """
    Create a new project.

    Args:
        data: Project creation data.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Created project.
    """
    project = Project(
        name=data.name,
        owner_id=current_user.user_id,
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    return ProjectResponse.model_validate(project)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project",
    description="Get a specific project by ID.",
    responses={
        404: {
            "description": "Project not found or not owned by user",
        },
    },
)
async def get_project(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectResponse:
    """
    Get a specific project.

    Args:
        project_id: Project UUID.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Project details.

    Raises:
        HTTPException: 404 if project not found or not owned by user.
    """
    project = await get_user_project(db, project_id, current_user)
    return ProjectResponse.model_validate(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project",
    description="Update a project's fields. Only provided fields are updated.",
    responses={
        404: {
            "description": "Project not found or not owned by user",
        },
    },
)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectResponse:
    """
    Update a project.

    Args:
        project_id: Project UUID.
        data: Fields to update.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Updated project.

    Raises:
        HTTPException: 404 if project not found or not owned by user.
    """
    project = await get_user_project(db, project_id, current_user)

    # Apply updates for provided fields
    if data.name is not None:
        project.name = data.name

    await db.commit()
    await db.refresh(project)

    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="Delete a project and all its associated data.",
    responses={
        404: {
            "description": "Project not found or not owned by user",
        },
    },
)
async def delete_project(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """
    Delete a project.

    Args:
        project_id: Project UUID.
        db: Database session.
        current_user: Current authenticated user.

    Raises:
        HTTPException: 404 if project not found or not owned by user.
    """
    project = await get_user_project(db, project_id, current_user)

    await db.delete(project)
    await db.commit()


# =============================================================================
# Site endpoints
# =============================================================================


@router.post(
    "/{project_id}/sites",
    response_model=SiteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add site",
    description="Add a site to a project.",
    responses={
        404: {
            "description": "Project not found or not owned by user",
        },
    },
)
async def add_site(
    project_id: UUID,
    data: SiteCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> SiteResponse:
    """
    Add a site to a project.

    Args:
        project_id: Project UUID.
        data: Site creation data.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Created site.

    Raises:
        HTTPException: 404 if project not found or not owned by user.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    site = Site(
        project_id=project_id,
        domain=data.domain,
        base_url=data.base_url,
    )

    db.add(site)
    await db.commit()
    await db.refresh(site)

    return SiteResponse.model_validate(site)


# =============================================================================
# Competitor endpoints
# =============================================================================


@router.post(
    "/{project_id}/competitors",
    response_model=CompetitorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add competitor",
    description="Add a competitor domain to a project.",
    responses={
        404: {
            "description": "Project not found or not owned by user",
        },
    },
)
async def add_competitor(
    project_id: UUID,
    data: CompetitorCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> CompetitorResponse:
    """
    Add a competitor to a project.

    Args:
        project_id: Project UUID.
        data: Competitor creation data.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Created competitor.

    Raises:
        HTTPException: 404 if project not found or not owned by user.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    competitor = Competitor(
        project_id=project_id,
        domain=data.domain,
    )

    db.add(competitor)
    await db.commit()
    await db.refresh(competitor)

    return CompetitorResponse.model_validate(competitor)


@router.get(
    "/{project_id}/competitors",
    response_model=CompetitorList,
    status_code=status.HTTP_200_OK,
    summary="List competitors",
    description="List all competitors for a project.",
    responses={
        404: {
            "description": "Project not found or not owned by user",
        },
    },
)
async def list_competitors(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> CompetitorList:
    """
    List all competitors for a project.

    Args:
        project_id: Project UUID.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        List of competitors.

    Raises:
        HTTPException: 404 if project not found or not owned by user.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    result = await db.execute(
        select(Competitor)
        .where(Competitor.project_id == project_id)
        .order_by(Competitor.created_at)
    )
    competitors = result.scalars().all()

    return CompetitorList(
        items=[CompetitorResponse.model_validate(c) for c in competitors]
    )
