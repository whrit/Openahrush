"""
Rate limit configuration and endpoint category mappings.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EndpointCategory(str, Enum):
    """Categories of endpoints with different rate limits."""

    AUTH = "auth"
    CRAWL_TRIGGER = "crawl_trigger"
    EXPORT_TRIGGER = "export_trigger"
    API_READ = "api_read"
    WEBHOOK_CONFIG = "webhook_config"


class RateLimitSettings(BaseSettings):
    """
    Rate limit settings loaded from environment variables.

    Defaults are optimized for typical API usage patterns:
    - Auth: 5/min to prevent brute force
    - Crawl triggers: 10/hour to manage server load
    - Export triggers: 20/hour for reasonable export volume
    - API reads: 100/min for responsive UIs
    - Webhook config: 10/min to prevent spam
    """

    model_config = SettingsConfigDict(
        env_prefix="RATE_LIMIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Auth endpoints: 5 per minute
    auth_limit: int = Field(default=5, ge=1, description="Max auth requests per window")
    auth_window_seconds: int = Field(default=60, ge=1, description="Auth rate limit window")

    # Crawl triggers: 10 per hour
    crawl_trigger_limit: int = Field(
        default=10, ge=1, description="Max crawl triggers per window"
    )
    crawl_trigger_window_seconds: int = Field(
        default=3600, ge=1, description="Crawl trigger rate limit window"
    )

    # Export triggers: 20 per hour
    export_trigger_limit: int = Field(
        default=20, ge=1, description="Max export triggers per window"
    )
    export_trigger_window_seconds: int = Field(
        default=3600, ge=1, description="Export trigger rate limit window"
    )

    # API reads: 100 per minute
    api_read_limit: int = Field(default=100, ge=1, description="Max API reads per window")
    api_read_window_seconds: int = Field(
        default=60, ge=1, description="API read rate limit window"
    )

    # Webhook config: 10 per minute
    webhook_config_limit: int = Field(
        default=10, ge=1, description="Max webhook config requests per window"
    )
    webhook_config_window_seconds: int = Field(
        default=60, ge=1, description="Webhook config rate limit window"
    )

    def get_limit_for_category(self, category: EndpointCategory) -> tuple[int, int]:
        """
        Get the rate limit and window for a given endpoint category.

        Args:
            category: The endpoint category.

        Returns:
            Tuple of (limit, window_seconds).
        """
        limits_map = {
            EndpointCategory.AUTH: (self.auth_limit, self.auth_window_seconds),
            EndpointCategory.CRAWL_TRIGGER: (
                self.crawl_trigger_limit,
                self.crawl_trigger_window_seconds,
            ),
            EndpointCategory.EXPORT_TRIGGER: (
                self.export_trigger_limit,
                self.export_trigger_window_seconds,
            ),
            EndpointCategory.API_READ: (self.api_read_limit, self.api_read_window_seconds),
            EndpointCategory.WEBHOOK_CONFIG: (
                self.webhook_config_limit,
                self.webhook_config_window_seconds,
            ),
        }
        return limits_map[category]


# Static endpoint to category mappings for exact paths
ENDPOINT_CATEGORY_MAPPINGS: dict[str, EndpointCategory] = {
    # Auth endpoints
    "/auth/login": EndpointCategory.AUTH,
    "/auth/register": EndpointCategory.AUTH,
    "/auth/refresh": EndpointCategory.AUTH,
    "/auth/forgot-password": EndpointCategory.AUTH,
    "/auth/reset-password": EndpointCategory.AUTH,
    # Crawl triggers (pattern-based, handled separately)
    "/projects/{project_id}/crawl": EndpointCategory.CRAWL_TRIGGER,
    "/projects/{project_id}/crawls": EndpointCategory.CRAWL_TRIGGER,
    # Export triggers
    "/projects/{project_id}/exports": EndpointCategory.EXPORT_TRIGGER,
    # Webhook config
    "/projects/{project_id}/webhooks": EndpointCategory.WEBHOOK_CONFIG,
}

# Compiled regex patterns for dynamic paths
_PATTERN_MAPPINGS: list[tuple[re.Pattern[str], str, EndpointCategory]] = [
    # Crawl triggers - POST only
    (
        re.compile(r"^/projects/[a-f0-9-]+/crawl$"),
        "POST",
        EndpointCategory.CRAWL_TRIGGER,
    ),
    (
        re.compile(r"^/projects/[a-f0-9-]+/crawls$"),
        "POST",
        EndpointCategory.CRAWL_TRIGGER,
    ),
    # Export triggers - POST only
    (
        re.compile(r"^/projects/[a-f0-9-]+/exports$"),
        "POST",
        EndpointCategory.EXPORT_TRIGGER,
    ),
    # Webhook config - POST/PUT/DELETE
    (
        re.compile(r"^/projects/[a-f0-9-]+/webhooks(/[a-f0-9-]+)?$"),
        "POST",
        EndpointCategory.WEBHOOK_CONFIG,
    ),
    (
        re.compile(r"^/projects/[a-f0-9-]+/webhooks(/[a-f0-9-]+)?$"),
        "PUT",
        EndpointCategory.WEBHOOK_CONFIG,
    ),
    (
        re.compile(r"^/projects/[a-f0-9-]+/webhooks(/[a-f0-9-]+)?$"),
        "DELETE",
        EndpointCategory.WEBHOOK_CONFIG,
    ),
]


def get_category_for_path(path: str, method: str) -> EndpointCategory | None:
    """
    Get the rate limit category for a given request path and method.

    Args:
        path: The request path (e.g., "/auth/login", "/projects/123/crawl").
        method: The HTTP method (GET, POST, etc.).

    Returns:
        The endpoint category, or None if no rate limit applies.
    """
    # Check exact path mappings first (for auth endpoints)
    if path in ENDPOINT_CATEGORY_MAPPINGS:
        category = ENDPOINT_CATEGORY_MAPPINGS[path]
        # Auth applies to all methods
        if category == EndpointCategory.AUTH:
            return category

    # Check pattern-based mappings
    for pattern, allowed_method, category in _PATTERN_MAPPINGS:
        if pattern.match(path) and method.upper() == allowed_method:
            return category

    # Default: GET requests are API reads
    if method.upper() == "GET":
        # Skip health/docs endpoints
        if path.startswith(("/health", "/docs", "/openapi", "/redoc")):
            return None
        return EndpointCategory.API_READ

    return None
