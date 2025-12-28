"""
Issue type model for issue taxonomy.

Defines the types of SEO issues that can be detected during crawls,
with categories, severity levels, and recommendations.
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from semrush_core.models.base import Base


class IssueCategory(str, Enum):
    """Issue category values."""

    CONTENT = "content"
    TECHNICAL = "technical"
    LINKS = "links"
    INDEXABILITY = "indexability"


class IssueType(Base):
    """
    Issue type model for issue taxonomy.

    Defines the catalog of SEO issues that can be detected,
    including severity levels and recommendations. This table
    is seeded with standard issue types during migrations.

    Attributes:
        id: String identifier for the issue type (e.g., 'missing_title').
        category: Issue category ('content', 'technical', 'links', 'indexability').
        severity: Severity level from 1 (low) to 5 (critical).
        name: Human-readable issue name.
        description: Detailed description of the issue.
        recommendation: How to fix the issue.
    """

    __tablename__ = "issue_types"

    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    severity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    recommendation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    @property
    def is_critical(self) -> bool:
        """Check if this is a critical severity issue (5)."""
        return self.severity == 5

    @property
    def is_high(self) -> bool:
        """Check if this is a high severity issue (4)."""
        return self.severity == 4

    @property
    def is_medium(self) -> bool:
        """Check if this is a medium severity issue (3)."""
        return self.severity == 3

    @property
    def is_low(self) -> bool:
        """Check if this is a low severity issue (2)."""
        return self.severity == 2

    @property
    def is_info(self) -> bool:
        """Check if this is an informational issue (1)."""
        return self.severity == 1

    @property
    def is_content_issue(self) -> bool:
        """Check if this is a content-related issue."""
        return self.category == IssueCategory.CONTENT.value

    @property
    def is_technical_issue(self) -> bool:
        """Check if this is a technical issue."""
        return self.category == IssueCategory.TECHNICAL.value

    @property
    def is_link_issue(self) -> bool:
        """Check if this is a link-related issue."""
        return self.category == IssueCategory.LINKS.value

    @property
    def is_indexability_issue(self) -> bool:
        """Check if this is an indexability issue."""
        return self.category == IssueCategory.INDEXABILITY.value


# MVP Issue Types for seeding
MVP_ISSUE_TYPES: list[dict] = [
    # Content Issues
    {
        "id": "missing_title",
        "category": IssueCategory.CONTENT.value,
        "severity": 4,
        "name": "Missing Title Tag",
        "description": "The page does not have a <title> tag.",
        "recommendation": "Add a unique, descriptive title tag between 50-60 characters.",
    },
    {
        "id": "duplicate_title",
        "category": IssueCategory.CONTENT.value,
        "severity": 3,
        "name": "Duplicate Title Tag",
        "description": "Multiple pages share the same title tag.",
        "recommendation": "Create unique titles for each page that accurately describe the content.",
    },
    {
        "id": "short_title",
        "category": IssueCategory.CONTENT.value,
        "severity": 2,
        "name": "Title Tag Too Short",
        "description": "The title tag is shorter than 30 characters.",
        "recommendation": "Expand the title to 50-60 characters for better visibility in search results.",
    },
    {
        "id": "long_title",
        "category": IssueCategory.CONTENT.value,
        "severity": 2,
        "name": "Title Tag Too Long",
        "description": "The title tag exceeds 60 characters and may be truncated.",
        "recommendation": "Shorten the title to 50-60 characters to prevent truncation.",
    },
    {
        "id": "missing_meta_description",
        "category": IssueCategory.CONTENT.value,
        "severity": 3,
        "name": "Missing Meta Description",
        "description": "The page does not have a meta description.",
        "recommendation": "Add a compelling meta description between 150-160 characters.",
    },
    {
        "id": "duplicate_meta_description",
        "category": IssueCategory.CONTENT.value,
        "severity": 2,
        "name": "Duplicate Meta Description",
        "description": "Multiple pages share the same meta description.",
        "recommendation": "Create unique meta descriptions for each page.",
    },
    {
        "id": "short_meta_description",
        "category": IssueCategory.CONTENT.value,
        "severity": 1,
        "name": "Meta Description Too Short",
        "description": "The meta description is shorter than 70 characters.",
        "recommendation": "Expand the description to 150-160 characters.",
    },
    {
        "id": "long_meta_description",
        "category": IssueCategory.CONTENT.value,
        "severity": 1,
        "name": "Meta Description Too Long",
        "description": "The meta description exceeds 160 characters.",
        "recommendation": "Shorten to 150-160 characters to prevent truncation.",
    },
    {
        "id": "missing_h1",
        "category": IssueCategory.CONTENT.value,
        "severity": 3,
        "name": "Missing H1 Tag",
        "description": "The page does not have an H1 heading.",
        "recommendation": "Add a single, descriptive H1 tag that includes the primary keyword.",
    },
    {
        "id": "multiple_h1",
        "category": IssueCategory.CONTENT.value,
        "severity": 2,
        "name": "Multiple H1 Tags",
        "description": "The page has more than one H1 tag.",
        "recommendation": "Use only one H1 tag per page for clear hierarchy.",
    },
    {
        "id": "thin_content",
        "category": IssueCategory.CONTENT.value,
        "severity": 3,
        "name": "Thin Content",
        "description": "The page has very little text content (under 200 words).",
        "recommendation": "Add more valuable, relevant content to the page.",
    },

    # Technical Issues
    {
        "id": "slow_response",
        "category": IssueCategory.TECHNICAL.value,
        "severity": 3,
        "name": "Slow Server Response",
        "description": "The server response time exceeds 500ms.",
        "recommendation": "Optimize server performance, consider caching and CDN.",
    },
    {
        "id": "missing_canonical",
        "category": IssueCategory.TECHNICAL.value,
        "severity": 2,
        "name": "Missing Canonical Tag",
        "description": "The page does not have a canonical tag.",
        "recommendation": "Add a canonical tag to prevent duplicate content issues.",
    },
    {
        "id": "canonical_mismatch",
        "category": IssueCategory.TECHNICAL.value,
        "severity": 3,
        "name": "Canonical URL Mismatch",
        "description": "The canonical URL points to a different page.",
        "recommendation": "Verify the canonical tag points to the correct URL.",
    },
    {
        "id": "redirect_chain",
        "category": IssueCategory.TECHNICAL.value,
        "severity": 3,
        "name": "Redirect Chain",
        "description": "The URL requires multiple redirects to reach the final page.",
        "recommendation": "Update links to point directly to the final URL.",
    },
    {
        "id": "redirect_loop",
        "category": IssueCategory.TECHNICAL.value,
        "severity": 5,
        "name": "Redirect Loop",
        "description": "The page is caught in an infinite redirect loop.",
        "recommendation": "Fix the redirect configuration to break the loop.",
    },
    {
        "id": "mixed_content",
        "category": IssueCategory.TECHNICAL.value,
        "severity": 3,
        "name": "Mixed Content",
        "description": "HTTPS page loads HTTP resources.",
        "recommendation": "Update all resource URLs to use HTTPS.",
    },

    # Link Issues
    {
        "id": "broken_internal_link",
        "category": IssueCategory.LINKS.value,
        "severity": 4,
        "name": "Broken Internal Link",
        "description": "An internal link returns a 4xx or 5xx error.",
        "recommendation": "Fix or remove the broken link.",
    },
    {
        "id": "broken_external_link",
        "category": IssueCategory.LINKS.value,
        "severity": 2,
        "name": "Broken External Link",
        "description": "An external link returns a 4xx or 5xx error.",
        "recommendation": "Remove or update the broken external link.",
    },
    {
        "id": "orphan_page",
        "category": IssueCategory.LINKS.value,
        "severity": 3,
        "name": "Orphan Page",
        "description": "The page has no internal links pointing to it.",
        "recommendation": "Add internal links from relevant pages.",
    },
    {
        "id": "too_many_links",
        "category": IssueCategory.LINKS.value,
        "severity": 1,
        "name": "Too Many Links on Page",
        "description": "The page contains more than 100 internal links.",
        "recommendation": "Consider reducing the number of links for better UX.",
    },

    # Indexability Issues
    {
        "id": "noindex",
        "category": IssueCategory.INDEXABILITY.value,
        "severity": 1,
        "name": "Page Set to Noindex",
        "description": "The page has a noindex directive.",
        "recommendation": "Verify this is intentional; remove if page should be indexed.",
    },
    {
        "id": "blocked_by_robots",
        "category": IssueCategory.INDEXABILITY.value,
        "severity": 2,
        "name": "Blocked by Robots.txt",
        "description": "The page is blocked from crawling by robots.txt.",
        "recommendation": "Update robots.txt if the page should be crawled.",
    },
    {
        "id": "4xx_error",
        "category": IssueCategory.INDEXABILITY.value,
        "severity": 4,
        "name": "4xx Client Error",
        "description": "The page returns a 4xx error status code.",
        "recommendation": "Fix the error or implement proper redirects.",
    },
    {
        "id": "5xx_error",
        "category": IssueCategory.INDEXABILITY.value,
        "severity": 5,
        "name": "5xx Server Error",
        "description": "The page returns a 5xx server error.",
        "recommendation": "Investigate and fix the server-side error.",
    },
    {
        "id": "soft_404",
        "category": IssueCategory.INDEXABILITY.value,
        "severity": 3,
        "name": "Soft 404",
        "description": "The page returns 200 status but appears to be an error page.",
        "recommendation": "Return proper 404 status or redirect to relevant content.",
    },
]
