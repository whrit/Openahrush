"""
Pydantic schemas for API request/response validation.

Organized by domain:
- auth: Authentication-related schemas (login, logout, user info)
- project: Project, Site, and Competitor schemas
- settings: Project settings schemas
"""

from semrush_api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    UserResponse,
)
from semrush_api.schemas.project import (
    CompetitorCreate,
    CompetitorList,
    CompetitorResponse,
    ProjectCreate,
    ProjectList,
    ProjectResponse,
    ProjectUpdate,
    SiteCreate,
    SiteList,
    SiteResponse,
)
from semrush_api.schemas.settings import (
    DEFAULT_SETTINGS,
    ProjectSettingsSchema,
    ProjectSettingsUpdate,
    SettingsUpdateResponse,
)

__all__ = [
    # Auth schemas
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    "UserResponse",
    # Project schemas
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    "ProjectList",
    "SiteCreate",
    "SiteResponse",
    "SiteList",
    "CompetitorCreate",
    "CompetitorResponse",
    "CompetitorList",
    # Settings schemas
    "ProjectSettingsSchema",
    "ProjectSettingsUpdate",
    "SettingsUpdateResponse",
    "DEFAULT_SETTINGS",
]
