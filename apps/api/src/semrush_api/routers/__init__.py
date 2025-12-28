"""
API Routers.

Contains all FastAPI routers organized by resource:
- health: Health check endpoints
- auth: Authentication endpoints (login, logout, me)
- settings: Project settings management
- projects: Project management
- crawls: Site crawl operations
- integrations: Third-party integrations (GSC, GA4, etc.)
- reports: Report generation and export
"""

from semrush_api.routers import auth, health, projects, settings

__all__ = [
    "auth",
    "health",
    "projects",
    "settings",
]
