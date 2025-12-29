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
- CrawlRun: Crawl job execution tracking
- CrawlPage: Per-page crawl results
- LinkEdge: Links discovered during crawls
- IssueType: Issue taxonomy (seeded)
- IssueInstance: SEO issues found during crawls
- SearchFactDaily: Search console metrics (GSC, BWT)
- AnalyticsFactDaily: Web analytics metrics (GA4)
- LinkFact: Backlink data from multiple sources
- AlertRule: User-configured alert rules
- Alert: Generated alerts
- CommonCrawlSnapshot: Common Crawl snapshot tracking
- CommonCrawlEdge: Raw backlink edges from Common Crawl
- CommonCrawlRefDomain: Aggregated referring domain data
- CommonCrawlAnchor: Aggregated anchor text data
- Export: Export job tracking for CSV/JSON/PDF generation
- WebhookConfig: Per-project webhook configuration
- WebhookDelivery: Webhook delivery tracking with retry support
- AuditLog: Security audit logging (imported from semrush_core.audit)
"""

# Import budget model early to ensure SQLAlchemy can resolve relationships
from semrush_core.budget.models import ProjectBudget
from semrush_core.models.alert import Alert, AlertEntityType, AlertKind, AlertSeverity
from semrush_core.models.alert_rule import AlertRule, AlertRuleType
from semrush_core.models.analytics_fact import AnalyticsFactDaily
from semrush_core.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from semrush_core.models.commoncrawl import (
    CommonCrawlAnchor,
    CommonCrawlEdge,
    CommonCrawlRefDomain,
    CommonCrawlSnapshot,
    SnapshotStatus,
)
from semrush_core.models.competitor import Competitor
from semrush_core.models.crawl_page import CrawlPage, RenderMode
from semrush_core.models.crawl_run import CrawlRun, CrawlStatus
from semrush_core.models.export import (
    Export,
    ExportFormat,
    ExportResource,
    ExportSchedule,
    ExportStatus,
)
from semrush_core.models.integration_account import IntegrationAccount, IntegrationProvider
from semrush_core.models.integration_mapping import IntegrationMapping
from semrush_core.models.integration_property import IntegrationProperty
from semrush_core.models.integration_token import IntegrationToken
from semrush_core.models.issue_instance import IssueInstance
from semrush_core.models.issue_type import MVP_ISSUE_TYPES, IssueCategory, IssueType
from semrush_core.models.link_edge import LinkEdge, LinkType
from semrush_core.models.link_fact import LinkFact, LinkSource, RelFlag
from semrush_core.models.project import Project
from semrush_core.models.project_backlink import BacklinkSourceType, ProjectBacklink
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
from semrush_core.models.webhook import (
    VALID_WEBHOOK_EVENTS,
    DeliveryStatus,
    WebhookConfig,
    WebhookDelivery,
)

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
    # Crawl models
    "CrawlRun",
    "CrawlStatus",
    "CrawlPage",
    "RenderMode",
    "LinkEdge",
    "LinkType",
    # Issue models
    "IssueType",
    "IssueCategory",
    "MVP_ISSUE_TYPES",
    "IssueInstance",
    # Fact table models
    "SearchFactDaily",
    "SearchEngine",
    "DeviceType",
    "SearchType",
    "AnalyticsFactDaily",
    "LinkFact",
    "LinkSource",
    "RelFlag",
    # Project backlink models
    "ProjectBacklink",
    "BacklinkSourceType",
    # Alert models
    "AlertRule",
    "AlertRuleType",
    "Alert",
    "AlertKind",
    "AlertSeverity",
    "AlertEntityType",
    # Common Crawl models
    "CommonCrawlSnapshot",
    "CommonCrawlEdge",
    "CommonCrawlRefDomain",
    "CommonCrawlAnchor",
    "SnapshotStatus",
    # Export models
    "Export",
    "ExportFormat",
    "ExportResource",
    "ExportSchedule",
    "ExportStatus",
    # Webhook models
    "WebhookConfig",
    "WebhookDelivery",
    "DeliveryStatus",
    "VALID_WEBHOOK_EVENTS",
    # Budget model
    "ProjectBudget",
    # NOTE: AuditLog and AuditAction are in semrush_core.audit module
    # to avoid circular imports. Import them from there:
    # from semrush_core.audit import AuditLog, AuditAction
]
