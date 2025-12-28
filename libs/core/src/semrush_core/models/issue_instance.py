"""
Issue instance model for per-page issues.

Stores detected issues for each page during a crawl,
with confidence scores, impact scores, and evidence.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.crawl_page import CrawlPage
    from semrush_core.models.crawl_run import CrawlRun
    from semrush_core.models.issue_type import IssueType


class IssueInstance(Base, UUIDMixin):
    """
    Issue instance model for per-page issues.

    Each issue instance represents a specific occurrence of an
    issue type on a particular page during a crawl run.

    Attributes:
        crawl_run_id: UUID of the parent crawl run.
        crawl_page_id: UUID of the page where issue was found.
        issue_type_id: String ID of the issue type (FK to issue_types).
        affected_url: URL where the issue was detected.
        confidence: Confidence score (0.000 to 1.000).
        impact_score: Calculated impact score.
        evidence: JSONB data with issue-specific details.
        crawl_run: Parent crawl run relationship.
        crawl_page: Parent crawl page relationship.
        issue_type: Issue type relationship.
    """

    __tablename__ = "issue_instances"

    crawl_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    crawl_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    issue_type_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("issue_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    affected_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3),  # 0.000 to 1.000
        nullable=True,
    )
    impact_score: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        index=True,
    )
    evidence: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )

    # Relationships
    crawl_run: Mapped[CrawlRun] = relationship(
        back_populates="issue_instances",
    )
    crawl_page: Mapped[CrawlPage] = relationship(
        back_populates="issues",
    )
    issue_type: Mapped[IssueType] = relationship()

    @property
    def is_high_confidence(self) -> bool:
        """Check if issue has high confidence (>= 0.9)."""
        if self.confidence is None:
            return False
        return self.confidence >= Decimal("0.900")

    @property
    def is_high_impact(self) -> bool:
        """Check if issue has high impact score (>= 75)."""
        if self.impact_score is None:
            return False
        return self.impact_score >= Decimal("75.00")

    @property
    def confidence_percent(self) -> float | None:
        """Get confidence as percentage (0-100)."""
        if self.confidence is None:
            return None
        return float(self.confidence * 100)

    @property
    def issue_key(self) -> tuple[str, str]:
        """
        Get the unique key for this issue.

        Used for comparing issues between crawl runs.

        Returns:
            Tuple of (issue_type_id, affected_url).
        """
        return (self.issue_type_id, self.affected_url)

    def get_evidence_value(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the evidence JSONB.

        Args:
            key: The key to look up.
            default: Default value if key not found.

        Returns:
            The value or default.
        """
        if self.evidence is None:
            return default
        return self.evidence.get(key, default)

    def set_evidence_value(self, key: str, value: Any) -> None:
        """
        Set a value in the evidence JSONB.

        Args:
            key: The key to set.
            value: The value to store.
        """
        if self.evidence is None:
            self.evidence = {}
        self.evidence[key] = value
