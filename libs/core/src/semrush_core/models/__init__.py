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
- IntegrationToken: Secure OAuth token storage
- IntegrationProperty: Discovered provider properties
- IntegrationMapping: Property-to-project mappings
- SyncRun: Sync job execution tracking
- SearchFactDaily: Search console metrics (GSC, BWT)
- AnalyticsFactDaily: Web analytics metrics (GA4)
- LinkFact: Backlink data from multiple sources
"""

from semrush_core.models.analytics_fact import AnalyticsFactDaily
from semrush_core.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from semrush_core.models.competitor import Competitor
from semrush_core.models.integration_account import IntegrationAccount, IntegrationProvider
from semrush_core.models.integration_mapping import IntegrationMapping
from semrush_core.models.integration_property import IntegrationProperty
from semrush_core.models.integration_token import IntegrationToken
from semrush_core.models.link_fact import LinkFact, LinkSource, RelFlag
from semrush_core.models.project import Project
from semrush_core.models.search_fact import (
    DeviceType,
    SearchEngine,
    SearchFactDaily,
    SearchType,
)
from semrush_core.models.settings import ProjectSettings
from semrush_core.models.site import Site
from semrush_core.models.sync_run import SyncMode, SyncRun, SyncStatus
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
    "IntegrationToken",
    "IntegrationProperty",
    "IntegrationMapping",
    # Sync models
    "SyncRun",
    "SyncMode",
    "SyncStatus",
    # Fact table models
    "SearchFactDaily",
    "SearchEngine",
    "DeviceType",
    "SearchType",
    "AnalyticsFactDaily",
    "LinkFact",
    "LinkSource",
    "RelFlag",
]
