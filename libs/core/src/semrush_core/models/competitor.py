"""
Competitor model for tracking competitor domains.

Competitors represent rival domains that users want to compare against
their own sites for SEO analysis.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.project import Project


class Competitor(Base, UUIDMixin, TimestampMixin):
    """
    Competitor model representing a competitor domain in a project.

    Competitors are domains that will be compared against the project's
    sites for keyword rankings, backlink analysis, and SEO metrics.

    Attributes:
        project_id: UUID of the parent project.
        domain: Competitor domain name (e.g., "competitor.com").
        project: Parent project this competitor belongs to.
    """

    __tablename__ = "competitors"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        back_populates="competitors",
    )
