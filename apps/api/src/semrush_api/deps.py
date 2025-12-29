"""
FastAPI dependency injection providers.

Provides reusable dependencies for:
- Database sessions
- Current user authentication
- Settings access
- Pagination
- Project access validation
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Path, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from semrush_core import Settings, get_settings
from semrush_core.database import get_async_session
from semrush_core.models import Project
from semrush_core.security.jwt import TokenData, TokenError, decode_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Security scheme for JWT bearer tokens
bearer_scheme = HTTPBearer(
    scheme_name="JWT",
    description="JWT Bearer token authentication",
    auto_error=False,
)


# Type aliases for commonly used dependencies
DbSession = Annotated[AsyncSession, Depends(get_async_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_current_user_optional(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> TokenData | None:
    """
    Get the current user from JWT token if provided.

    Does not raise an error if no token is provided, making authentication
    optional for the endpoint.

    Args:
        credentials: Bearer token credentials from request header.

    Returns:
        TokenData if valid token provided, None otherwise.

    Raises:
        HTTPException: If token is provided but invalid.
    """
    if credentials is None:
        return None

    try:
        return decode_token(credentials.credentials, required_type="access")
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(
    token_data: Annotated[TokenData | None, Depends(get_current_user_optional)],
) -> TokenData:
    """
    Get the current authenticated user.

    Requires a valid JWT token. Use this dependency for endpoints
    that require authentication.

    Args:
        token_data: Token data from optional auth dependency.

    Returns:
        TokenData with user information.

    Raises:
        HTTPException: If no token provided or token is invalid.
    """
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data


# Type alias for current user dependency
CurrentUser = Annotated[TokenData, Depends(get_current_user)]
OptionalUser = Annotated[TokenData | None, Depends(get_current_user_optional)]


def require_scopes(*required_scopes: str):
    """
    Create a dependency that requires specific scopes.

    Use as a dependency to enforce scope-based authorization.

    Args:
        *required_scopes: Scopes that the user must have.

    Returns:
        Dependency function that validates scopes.

    Example:
        @router.delete("/admin/user/{user_id}")
        async def delete_user(
            user_id: UUID,
            current_user: CurrentUser,
            _: Annotated[None, Depends(require_scopes("admin", "users:delete"))],
        ):
            ...
    """

    async def scope_validator(current_user: CurrentUser) -> None:
        user_scopes = set(current_user.scopes)
        missing = set(required_scopes) - user_scopes

        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scopes: {', '.join(sorted(missing))}",
            )

    return scope_validator


class PaginationParams:
    """
    Pagination parameters for list endpoints.

    Provides consistent pagination across all list endpoints with
    reasonable defaults and limits.

    Attributes:
        page: Page number (1-indexed).
        page_size: Number of items per page.
        offset: Calculated offset for database queries.
    """

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
        page_size: Annotated[
            int,
            Query(ge=1, le=100, alias="pageSize", description="Items per page"),
        ] = 20,
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        """Calculate the offset for database queries."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get the limit for database queries."""
        return self.page_size


Pagination = Annotated[PaginationParams, Depends()]


class SortParams:
    """
    Sorting parameters for list endpoints.

    Provides consistent sorting options with validation.

    Attributes:
        sort_by: Field to sort by.
        sort_order: Sort direction (asc/desc).
    """

    def __init__(
        self,
        sort_by: Annotated[
            str | None,
            Query(alias="sortBy", description="Field to sort by"),
        ] = None,
        sort_order: Annotated[
            str,
            Query(
                alias="sortOrder",
                pattern="^(asc|desc)$",
                description="Sort direction",
            ),
        ] = "desc",
    ) -> None:
        self.sort_by = sort_by
        self.sort_order = sort_order

    @property
    def is_ascending(self) -> bool:
        """Check if sort order is ascending."""
        return self.sort_order == "asc"


Sort = Annotated[SortParams, Depends()]


async def get_request_id(
    x_request_id: Annotated[
        str | None,
        Header(description="Request ID for tracing"),
    ] = None,
) -> str | None:
    """
    Get request ID from header for tracing.

    Args:
        x_request_id: Request ID header value.

    Returns:
        Request ID if provided.
    """
    return x_request_id


RequestId = Annotated[str | None, Depends(get_request_id)]


def validate_project_access(project_id: UUID, current_user: CurrentUser) -> UUID:
    """
    Validate that the current user has access to a project.

    This is a placeholder for project access validation. The actual
    implementation should check project membership in the database.

    Args:
        project_id: Project to validate access for.
        current_user: Current authenticated user.

    Returns:
        The project ID if access is granted.

    Raises:
        HTTPException: If user doesn't have access to the project.
    """
    # TODO: Implement actual project access check
    # For now, return the project_id (authentication is enough)
    return project_id


# =============================================================================
# Project Access Dependencies
# =============================================================================


async def get_user_project(
    project_id: Annotated[UUID, Path(description="Project UUID")],
    db: DbSession,
    current_user: CurrentUser,
) -> Project:
    """
    Get a project owned by the current user.

    This is a reusable FastAPI dependency that fetches a project by ID
    and validates that the current authenticated user owns it. Use this
    dependency in any endpoint that requires project access verification.

    Args:
        project_id: Project UUID from path parameter.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Project if found and owned by user.

    Raises:
        HTTPException: 404 if project not found or not owned by user.

    Example:
        @router.get("/{project_id}/details")
        async def get_project_details(
            project: Annotated[Project, Depends(get_user_project)],
        ) -> ProjectResponse:
            return ProjectResponse.model_validate(project)
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


# Type alias for user project dependency
UserProject = Annotated[Project, Depends(get_user_project)]
