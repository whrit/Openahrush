"""
Diffs API endpoints.

Provides endpoints for:
- GET /projects/{project_id}/issues/diffs - Compare issues between crawl runs
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from semrush_core.models import CrawlRun, IssueInstance, Project
from semrush_workers.diff.diff_engine import DiffEngine, IssueData
from sqlalchemy import select

from semrush_api.deps import CurrentUser, DbSession

router = APIRouter(prefix="/projects", tags=["Diffs"])


class IssueDiffItem(BaseModel):
    """Issue item in diff response."""

    id: str
    issue_type_id: str
    affected_url: str
    severity: str
    confidence: float | None = None
    message: str | None = None


class ChangedIssueItem(BaseModel):
    """Changed issue item in diff response."""

    before: IssueDiffItem
    after: IssueDiffItem
    severity_changed: bool
    confidence_changed: bool


class DiffSummary(BaseModel):
    """Summary of diff results."""

    added_count: int
    resolved_count: int
    changed_count: int
    total_changes: int


class DiffResponse(BaseModel):
    """Response for diffs endpoint."""

    added: list[IssueDiffItem]
    resolved: list[IssueDiffItem]
    changed: list[ChangedIssueItem]
    summary: DiffSummary


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


async def get_crawl_run(
    db: DbSession,
    crawl_run_id: UUID,
) -> CrawlRun | None:
    """
    Get a crawl run by ID.

    Args:
        db: Database session.
        crawl_run_id: Crawl run UUID.

    Returns:
        CrawlRun if found, None otherwise.
    """
    result = await db.execute(select(CrawlRun).where(CrawlRun.id == crawl_run_id))
    return result.scalar_one_or_none()


async def get_issues_for_crawl(
    db: DbSession,
    crawl_run_id: UUID,
) -> list[IssueInstance]:
    """
    Get all issues for a crawl run.

    Args:
        db: Database session.
        crawl_run_id: Crawl run UUID.

    Returns:
        List of issues for the crawl run.
    """
    result = await db.execute(
        select(IssueInstance).where(IssueInstance.crawl_run_id == crawl_run_id)
    )
    return list(result.scalars().all())


def issue_to_data(issue: IssueInstance) -> IssueData:
    """Convert IssueInstance to IssueData for diffing."""
    confidence: Decimal | None = None
    if hasattr(issue, "confidence") and issue.confidence is not None:
        confidence = Decimal(str(issue.confidence))
    message: str | None = None
    if hasattr(issue, "message"):
        message = issue.message

    return IssueData(
        id=issue.id,
        issue_type_id=issue.issue_type_id,
        affected_url=issue.affected_url,
        severity=getattr(issue, "severity", "warning"),
        confidence=confidence,
        message=message,
    )


@router.get(
    "/{project_id}/issues/diffs",
    response_model=DiffResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare issues between crawl runs",
    description="Get the diff of issues between two crawl runs.",
    responses={
        400: {"description": "Crawl runs are not from the same project"},
        404: {"description": "Project or crawl run not found"},
    },
)
async def get_issues_diff(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    from_crawl_run_id: UUID = Query(
        ...,
        description="UUID of the first (older) crawl run",
    ),
    to_crawl_run_id: UUID = Query(
        ...,
        description="UUID of the second (newer) crawl run",
    ),
) -> dict[str, Any]:
    """
    Compare issues between two crawl runs.

    Returns the diff showing:
    - Added issues (in to_crawl but not in from_crawl)
    - Resolved issues (in from_crawl but not in to_crawl)
    - Changed issues (severity or confidence changed)

    Args:
        project_id: Project UUID.
        db: Database session.
        current_user: Current authenticated user.
        from_crawl_run_id: First (older) crawl run UUID.
        to_crawl_run_id: Second (newer) crawl run UUID.

    Returns:
        Diff result with added, resolved, and changed issues.

    Raises:
        HTTPException: 400 if crawl runs are from different projects.
        HTTPException: 404 if project or crawl runs not found.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Get crawl runs
    crawl_a = await get_crawl_run(db, from_crawl_run_id)
    if crawl_a is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crawl run {from_crawl_run_id} not found",
        )

    crawl_b = await get_crawl_run(db, to_crawl_run_id)
    if crawl_b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crawl run {to_crawl_run_id} not found",
        )

    # Verify both crawl runs are from the same project
    if crawl_a.project_id != crawl_b.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Crawl runs must be from the same project",
        )

    # Verify crawl runs belong to the requested project
    if crawl_a.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Crawl runs do not belong to this project",
        )

    # Get issues for both crawl runs
    issues_a = await get_issues_for_crawl(db, from_crawl_run_id)
    issues_b = await get_issues_for_crawl(db, to_crawl_run_id)

    # Convert to IssueData for diffing
    data_a = [issue_to_data(issue) for issue in issues_a]
    data_b = [issue_to_data(issue) for issue in issues_b]

    # Compute diff
    engine = DiffEngine()
    result = engine.compute_diff(data_a, data_b)

    return result.to_dict()
