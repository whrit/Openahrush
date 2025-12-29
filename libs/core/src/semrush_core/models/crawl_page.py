"""
Crawl page model for per-page crawl results.

Stores the crawl result for each URL discovered during a crawl run,
including HTTP response data, extracted SEO fields, and artifact references.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.crawl_run import CrawlRun
    from semrush_core.models.issue_instance import IssueInstance


class RenderMode(str, Enum):
    """Page render mode values."""

    HTML = "html"
    JS = "js"


class CrawlPage(Base, UUIDMixin):
    """
    Crawl page model for per-page crawl results.

    Each crawl page represents the result of crawling a single URL,
    including HTTP response data, extracted SEO fields, content hashes,
    and references to stored artifacts.

    Attributes:
        crawl_run_id: UUID of the parent crawl run.
        url: Original URL that was crawled.
        final_url: Final URL after any redirects.
        status_code: HTTP response status code.
        content_type: HTTP Content-Type header.
        response_time_ms: Response time in milliseconds.
        render_mode: Render mode used ('html' or 'js').
        title: Extracted <title> tag content.
        meta_description: Extracted meta description.
        canonical_url: Extracted canonical URL.
        meta_robots: Extracted robots meta tag content.
        h1_count: Number of H1 tags on page.
        first_h1: Content of first H1 tag.
        word_count: Number of words in main content.
        text_length: Character count of visible text.
        html_hash: Hash of raw HTML content.
        rendered_hash: Hash of rendered HTML (after JS).
        content_hash: Hash of extracted text content.
        html_artifact_key: S3/MinIO key for stored HTML.
        rendered_artifact_key: S3/MinIO key for rendered HTML.
        was_rendered: Whether page was JS-rendered.
        render_trigger: Reason for JS rendering.
        crawl_run: Parent crawl run relationship.
        issues: Issue instances found on this page.
    """

    __tablename__ = "crawl_pages"

    crawl_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    final_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    content_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    response_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    render_mode: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    # Extracted SEO fields
    title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    meta_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    canonical_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    meta_robots: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    h1_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    first_h1: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    word_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    text_length: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Content hashes
    html_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    rendered_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # Artifact references
    html_artifact_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    rendered_artifact_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Render tracking
    was_rendered: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
    )
    render_trigger: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Relationships
    crawl_run: Mapped[CrawlRun] = relationship(
        back_populates="pages",
    )
    issues: Mapped[list[IssueInstance]] = relationship(
        back_populates="crawl_page",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    @property
    def is_success(self) -> bool:
        """Check if page returned a 2xx status code."""
        if self.status_code is None:
            return False
        return 200 <= self.status_code < 300

    @property
    def is_redirect(self) -> bool:
        """Check if page returned a 3xx redirect status."""
        if self.status_code is None:
            return False
        return 300 <= self.status_code < 400

    @property
    def is_client_error(self) -> bool:
        """Check if page returned a 4xx client error."""
        if self.status_code is None:
            return False
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """Check if page returned a 5xx server error."""
        if self.status_code is None:
            return False
        return 500 <= self.status_code < 600

    @property
    def was_js_rendered(self) -> bool:
        """Check if page was rendered with JavaScript."""
        return self.render_mode == RenderMode.JS.value

    @property
    def has_title(self) -> bool:
        """Check if page has a title tag."""
        return self.title is not None and len(self.title.strip()) > 0

    @property
    def has_meta_description(self) -> bool:
        """Check if page has a meta description."""
        return self.meta_description is not None and len(self.meta_description.strip()) > 0

    @property
    def has_canonical(self) -> bool:
        """Check if page has a canonical URL."""
        return self.canonical_url is not None and len(self.canonical_url.strip()) > 0

    @property
    def is_self_canonical(self) -> bool:
        """Check if canonical URL points to self."""
        if not self.has_canonical:
            return False
        # Compare normalized URLs
        return self.canonical_url == self.url or self.canonical_url == self.final_url

    @property
    def is_noindex(self) -> bool:
        """Check if page has noindex directive."""
        if self.meta_robots is None:
            return False
        return "noindex" in self.meta_robots.lower()

    @property
    def is_nofollow(self) -> bool:
        """Check if page has nofollow directive."""
        if self.meta_robots is None:
            return False
        return "nofollow" in self.meta_robots.lower()
