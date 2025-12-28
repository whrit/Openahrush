"""
API Routers.

Contains all FastAPI routers organized by resource:
- health: Health check endpoints
- auth: Authentication endpoints (login, logout, me)
- settings: Project settings management
- projects: Project management
- integrations: Third-party integrations (GSC, GA4, etc.)
- crawls: Site crawl operations
- reports: Report generation and export
"""

from semrush_api.routers import auth, health, integrations, projects, settings

__all__ = [
    "auth",
    "health",
    "integrations",
    "projects",
    "settings",
]
