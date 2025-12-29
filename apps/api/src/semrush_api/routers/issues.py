"""
Issues API endpoints.

Provides endpoints for:
- GET /crawls/{crawl_run_id}/issues - List issues for a crawl
- GET /projects/{project_id}/issues - Get issues from latest crawl
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from semrush_core.models import CrawlRun, IssueInstance, IssueType, Project
from sqlalchemy import desc, func, select

from semrush_api.deps import CurrentUser, DbSession, Pagination, Sort, UserProject
from semrush_api.schemas.issues import (
    IssueInstanceResponse,
    IssueListResponse,
    IssueTypeResponse,
)

router = APIRouter(tags=["Issues"])


async def get_crawl_run_with_auth(
    db: DbSession,
    crawl_run_id: UUID,
    current_user: CurrentUser,
) -> CrawlRun:
    """
    Get a crawl run, verifying user ownership of the parent project.

    Args:
        db: Database session.
        crawl_run_id: Crawl run UUID.
        current_user: Current authenticated user.

    Returns:
        CrawlRun if found and user owns parent project.

    Raises:
        HTTPException: 404 if not found or unauthorized.
    """
    # Get crawl run
    result = await db.execute(select(CrawlRun).where(CrawlRun.id == crawl_run_id))
    crawl_run = result.scalar_one_or_none()

    if crawl_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crawl run not found",
        )

    # Verify project ownership
    project_result = await db.execute(
        select(Project).where(
            Project.id == crawl_run.project_id,
            Project.owner_id == current_user.user_id,
        )
    )
    project = project_result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crawl run not found",
        )

    return crawl_run


def build_issue_response(
    issue: IssueInstance,
    include_type: bool = False,
) -> IssueInstanceResponse:
    """
    Build an IssueInstanceResponse from an IssueInstance model.

    Args:
        issue: Database model instance.
        include_type: Whether to include issue type details.

    Returns:
        Pydantic response model.
    """
    issue_type_response = None
    if include_type and hasattr(issue, "issue_type") and issue.issue_type:
        issue_type_response = IssueTypeResponse(
            id=issue.issue_type.id,
            category=issue.issue_type.category,
            severity=issue.issue_type.severity,
            name=issue.issue_type.name,
            description=issue.issue_type.description,
            recommendation=issue.issue_type.recommendation,
        )

    # Get severity from issue_type if available
    severity = 3  # Default to medium
    if hasattr(issue, "issue_type") and issue.issue_type:
        severity = issue.issue_type.severity

    return IssueInstanceResponse(
        id=issue.id,
        crawl_run_id=issue.crawl_run_id,
        crawl_page_id=issue.crawl_page_id,
        issue_type_id=issue.issue_type_id,
        affected_url=issue.affected_url,
        confidence=float(issue.confidence) if issue.confidence else 1.0,
        impact_score=float(issue.impact_score) if issue.impact_score else None,
        severity=severity,
        evidence=issue.evidence or {},
        created_at=issue.crawl_run.created_at,  # Use crawl run timestamp
        issue_type=issue_type_response,
    )


@router.get(
    "/crawls/{crawl_run_id}/issues",
    response_model=IssueListResponse,
    status_code=status.HTTP_200_OK,
    summary="List crawl issues",
    description="List all issues found during a specific crawl run.",
    responses={
        404: {"description": "Crawl run not found or not owned by user"},
    },
)
async def list_crawl_issues(
    crawl_run_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    pagination: Pagination,
    sort: Sort,
    issue_type_id: Annotated[
        str | None,
        Query(alias="issueTypeId", description="Filter by issue type ID"),
    ] = None,
    severity: Annotated[
        int | None,
        Query(ge=1, le=5, description="Filter by severity level"),
    ] = None,
) -> IssueListResponse:
    """
    List all issues for a specific crawl run.

    Args:
        crawl_run_id: Crawl run UUID.
        db: Database session.
        current_user: Current authenticated user.
        pagination: Pagination parameters.
        sort: Sorting parameters.
        issue_type_id: Filter by issue type.
        severity: Filter by severity level.

    Returns:
        Paginated list of issues.
    """
    # Verify access
    await get_crawl_run_with_auth(db, crawl_run_id, current_user)

    # Build base query
    base_query = select(IssueInstance).where(IssueInstance.crawl_run_id == crawl_run_id)

    # Track if we've joined with IssueType
    has_issue_type_join = False

    # Apply filters
    if issue_type_id:
        base_query = base_query.where(IssueInstance.issue_type_id == issue_type_id)

    if severity:
        # Join with issue_types to filter by severity
        base_query = base_query.join(IssueType).where(IssueType.severity == severity)
        has_issue_type_join = True

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Apply sorting
    if sort.sort_by == "impact_score" or sort.sort_by is None:
        order_column = IssueInstance.impact_score
    elif sort.sort_by == "severity":
        # Need to join with issue_types for severity sort
        if not has_issue_type_join:
            base_query = base_query.join(IssueType)
            has_issue_type_join = True
        order_column = IssueType.severity
    elif sort.sort_by == "category":
        if not has_issue_type_join:
            base_query = base_query.join(IssueType)
            has_issue_type_join = True
        order_column = IssueType.category
    else:
        order_column = IssueInstance.impact_score

    if sort.is_ascending:
        base_query = base_query.order_by(order_column.asc().nullslast())
    else:
        base_query = base_query.order_by(order_column.desc().nullslast())

    # Apply pagination
    base_query = base_query.offset(pagination.offset).limit(pagination.limit)

    # Execute
    result = await db.execute(base_query)
    issues = result.scalars().all()

    # Build response
    items = [build_issue_response(issue, include_type=True) for issue in issues]

    return IssueListResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/projects/{project_id}/issues",
    response_model=IssueListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project issues",
    description="Get issues from the latest crawl run for a project.",
    responses={
        404: {"description": "Project not found, not owned by user, or no crawl runs exist"},
    },
)
async def get_project_issues(
    db: DbSession,
    project: UserProject,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum number of issues to return"),
    ] = 20,
) -> IssueListResponse:
    """
    Get issues from the latest crawl run for a project.

    Returns issues sorted by impact_score descending.

    Args:
        db: Database session.
        project: Project retrieved via dependency (validates ownership).
        limit: Maximum number of issues to return.

    Returns:
        List of top issues from latest crawl.

    Raises:
        HTTPException: 404 if project not found or no crawl runs exist.
    """
    # Get latest completed crawl run
    crawl_result = await db.execute(
        select(CrawlRun)
        .where(
            CrawlRun.project_id == project.id,
            CrawlRun.status == "completed",
        )
        .order_by(desc(CrawlRun.created_at))
        .limit(1)
    )
    crawl_run = crawl_result.scalar_one_or_none()

    if crawl_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed crawl runs found for this project",
        )

    # Get issues sorted by impact score
    issues_result = await db.execute(
        select(IssueInstance)
        .where(IssueInstance.crawl_run_id == crawl_run.id)
        .order_by(desc(IssueInstance.impact_score).nullslast())
        .limit(limit)
    )
    issues = issues_result.scalars().all()

    # Build response
    items = [build_issue_response(issue, include_type=True) for issue in issues]

    return IssueListResponse(
        items=items,
        total=len(items),
        page=1,
        page_size=limit,
    )
