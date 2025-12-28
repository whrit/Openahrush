"""
Project settings schemas for API request/response validation.

Contains Pydantic models for:
- ProjectSettingsSchema: Complete settings with all fields and validation
- ProjectSettingsUpdate: Partial update schema with optional fields
- Default settings for new projects
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectSettingsSchema(BaseModel):
    """
    Complete project settings schema with all fields and validation.

    Covers:
    - Scope settings: seed URL, subdomains, allowed hosts, regexes
    - Query parameter settings: policies and lists
    - Crawl budget settings: max pages, depth, concurrency, etc.
    - JS rendering settings: mode, budgets, selectors
    - Schedule settings: audit, sync, refresh frequencies
    - Retention settings: how long to keep data
    """

    model_config = ConfigDict(extra="forbid")

    # Scope settings
    seed_url: str = Field(..., description="Seed URL for crawling")
    include_subdomains: bool = Field(
        default=True,
        description="Whether to include subdomains in crawl scope",
    )
    allowed_hosts: list[str] = Field(
        default_factory=list,
        description="Additional hosts allowed in crawl scope",
    )
    allowed_schemes: list[str] = Field(
        default=["https", "http"],
        description="URL schemes to allow",
    )
    include_regexes: list[str] = Field(
        default_factory=list,
        description="URL patterns to include (regex)",
    )
    exclude_regexes: list[str] = Field(
        default_factory=list,
        description="URL patterns to exclude (regex)",
    )

    # Query parameter settings
    query_param_policy: Literal["allow_all", "strip_all", "allowlist", "denylist"] = Field(
        default="strip_all",
        description="How to handle query parameters",
    )
    query_param_allowlist: list[str] = Field(
        default_factory=list,
        description="Query params to keep (when policy=allowlist)",
    )
    query_param_denylist: list[str] = Field(
        default_factory=list,
        description="Query params to remove (when policy=denylist)",
    )
    strip_tracking_params: bool = Field(
        default=True,
        description="Whether to strip common tracking parameters (utm_*, fbclid, etc.)",
    )

    # Crawl budget settings
    max_pages: int = Field(
        default=5000,
        ge=1,
        le=100000,
        description="Maximum number of pages to crawl",
    )
    max_depth: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Maximum link depth from seed URL",
    )
    concurrency_html: int = Field(
        default=16,
        ge=1,
        le=100,
        description="Number of concurrent HTML requests",
    )
    politeness_delay_ms: int = Field(
        default=0,
        ge=0,
        le=10000,
        description="Delay between requests in milliseconds",
    )
    respect_robots: bool = Field(
        default=True,
        description="Whether to respect robots.txt directives",
    )
    use_sitemaps: bool = Field(
        default=True,
        description="Whether to discover URLs from sitemaps",
    )
    user_agent: str = Field(
        default="openahrush/0.1",
        description="User-Agent string for requests",
    )

    # JS rendering settings
    js_render_mode: Literal["off", "hybrid", "js_only"] = Field(
        default="hybrid",
        description="JavaScript rendering mode",
    )
    max_rendered_pages: int = Field(
        default=200,
        ge=0,
        le=10000,
        description="Maximum pages to render with JS",
    )
    max_render_time_ms: int = Field(
        default=15000,
        ge=1000,
        le=60000,
        description="Maximum time to wait for JS rendering",
    )
    concurrency_js: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Number of concurrent browser instances",
    )
    required_selectors: list[str] = Field(
        default_factory=list,
        description="CSS selectors that must be present after JS render",
    )

    # Schedule settings
    audit_frequency: Literal["off", "daily", "weekly"] = Field(
        default="weekly",
        description="How often to run site audits",
    )
    integration_sync_frequency: Literal["daily", "weekly"] = Field(
        default="daily",
        description="How often to sync integration data",
    )
    visibility_refresh_frequency: Literal["daily", "weekly"] = Field(
        default="daily",
        description="How often to refresh visibility data",
    )
    links_refresh_frequency: Literal["off", "monthly"] = Field(
        default="monthly",
        description="How often to refresh backlink data",
    )

    # Retention settings
    retain_audit_runs: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of audit runs to retain",
    )
    retain_serp_snapshots_days: int = Field(
        default=90,
        ge=0,
        le=365,
        description="Days to retain SERP snapshots",
    )
    retain_raw_html_days: int = Field(
        default=0,
        ge=0,
        le=90,
        description="Days to retain raw HTML (0 = do not store)",
    )

    @field_validator("seed_url")
    @classmethod
    def validate_seed_url(cls, v: str) -> str:
        """Validate that seed_url starts with http:// or https://."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("seed_url must start with http:// or https://")
        return v

    @field_validator("include_regexes", "exclude_regexes")
    @classmethod
    def validate_regexes(cls, v: list[str]) -> list[str]:
        """Validate that all regex patterns are valid."""
        for pattern in v:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{pattern}': {e}") from e
        return v

    @field_validator("required_selectors")
    @classmethod
    def validate_selectors(cls, v: list[str]) -> list[str]:
        """Validate that CSS selectors are not empty."""
        for selector in v:
            if not selector.strip():
                raise ValueError("Empty selector not allowed")
        return v


class ProjectSettingsUpdate(BaseModel):
    """
    Partial update schema for project settings.

    All fields are optional to allow partial updates.
    The API merges provided fields with existing settings.
    """

    model_config = ConfigDict(extra="forbid")

    # Scope settings
    seed_url: str | None = None
    include_subdomains: bool | None = None
    allowed_hosts: list[str] | None = None
    allowed_schemes: list[str] | None = None
    include_regexes: list[str] | None = None
    exclude_regexes: list[str] | None = None

    # Query parameter settings
    query_param_policy: Literal["allow_all", "strip_all", "allowlist", "denylist"] | None = None
    query_param_allowlist: list[str] | None = None
    query_param_denylist: list[str] | None = None
    strip_tracking_params: bool | None = None

    # Crawl budget settings
    max_pages: int | None = Field(default=None, ge=1, le=100000)
    max_depth: int | None = Field(default=None, ge=1, le=20)
    concurrency_html: int | None = Field(default=None, ge=1, le=100)
    politeness_delay_ms: int | None = Field(default=None, ge=0, le=10000)
    respect_robots: bool | None = None
    use_sitemaps: bool | None = None
    user_agent: str | None = None

    # JS rendering settings
    js_render_mode: Literal["off", "hybrid", "js_only"] | None = None
    max_rendered_pages: int | None = Field(default=None, ge=0, le=10000)
    max_render_time_ms: int | None = Field(default=None, ge=1000, le=60000)
    concurrency_js: int | None = Field(default=None, ge=1, le=10)
    required_selectors: list[str] | None = None

    # Schedule settings
    audit_frequency: Literal["off", "daily", "weekly"] | None = None
    integration_sync_frequency: Literal["daily", "weekly"] | None = None
    visibility_refresh_frequency: Literal["daily", "weekly"] | None = None
    links_refresh_frequency: Literal["off", "monthly"] | None = None

    # Retention settings
    retain_audit_runs: int | None = Field(default=None, ge=1, le=100)
    retain_serp_snapshots_days: int | None = Field(default=None, ge=0, le=365)
    retain_raw_html_days: int | None = Field(default=None, ge=0, le=90)

    @field_validator("seed_url")
    @classmethod
    def validate_seed_url(cls, v: str | None) -> str | None:
        """Validate that seed_url starts with http:// or https:// if provided."""
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("seed_url must start with http:// or https://")
        return v

    @field_validator("include_regexes", "exclude_regexes")
    @classmethod
    def validate_regexes(cls, v: list[str] | None) -> list[str] | None:
        """Validate that all regex patterns are valid if provided."""
        if v is not None:
            for pattern in v:
                try:
                    re.compile(pattern)
                except re.error as e:
                    raise ValueError(f"Invalid regex pattern '{pattern}': {e}") from e
        return v

    @field_validator("required_selectors")
    @classmethod
    def validate_selectors(cls, v: list[str] | None) -> list[str] | None:
        """Validate that CSS selectors are not empty if provided."""
        if v is not None:
            for selector in v:
                if not selector.strip():
                    raise ValueError("Empty selector not allowed")
        return v


class SettingsUpdateResponse(BaseModel):
    """Response for successful settings update."""

    ok: bool = True
    message: str = "Settings updated successfully"


# Default settings for new projects
DEFAULT_SETTINGS: dict[str, Any] = ProjectSettingsSchema(
    seed_url="https://example.com"
).model_dump()
