"""
API Routers.

Contains all FastAPI routers organized by resource:
- health: Health check endpoints
- auth: Authentication endpoints (login, logout, me)
- settings: Project settings management
- projects: Project management
- integrations: Third-party integrations (GSC, GA4, etc.)
- diffs: Issue diff comparison
- alerts: Alert management
- crawls: Site crawl operations
- reports: Report generation and export
- webhooks: Webhook configuration and delivery
- schedules: Export schedule management
"""

from semrush_api.routers import (
    alerts,
    auth,
    diffs,
    health,
    integrations,
    issues,
    projects,
    schedules,
    settings,
    webhooks,
)

__all__ = [
    "alerts",
    "auth",
    "diffs",
    "health",
    "integrations",
    "issues",
    "projects",
    "schedules",
    "settings",
    "webhooks",
]
