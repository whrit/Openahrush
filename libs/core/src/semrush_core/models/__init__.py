"""
SQLAlchemy models for Openahrush.

All models inherit from Base and include common mixins for:
- UUID primary keys
- Created/updated timestamps
- Soft delete support (where applicable)

Models are organized by domain:
- User: Authentication and user management
- Project: SEO project containers
- Site: Domains being monitored
- Competitor: Competitor domains for comparison
- ProjectSettings: Project-specific configuration
- IntegrationAccount: OAuth-linked third-party services
"""

from semrush_core.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from semrush_core.models.competitor import Competitor
from semrush_core.models.integration_account import IntegrationAccount, IntegrationProvider
from semrush_core.models.project import Project
from semrush_core.models.settings import ProjectSettings
from semrush_core.models.site import Site
from semrush_core.models.user import User

__all__ = [
    # Base and mixins
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    # Core models
    "User",
    "Project",
    "Site",
    "Competitor",
    "ProjectSettings",
    # Integration models
    "IntegrationAccount",
    "IntegrationProvider",
]
