"""
Site model for domains being monitored.

Sites represent the primary domains that users want to track, crawl,
and analyze for SEO purposes.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.project import Project


class Site(Base, UUIDMixin, TimestampMixin):
    """
    Site model representing a domain being monitored in a project.

    Each site belongs to a project and represents a domain that will
    be crawled, audited, and analyzed.

    Attributes:
        project_id: UUID of the parent project.
        domain: Domain name (e.g., "example.com").
        base_url: Full URL to start crawling from (e.g., "https://www.example.com").
        project: Parent project this site belongs to.
    """

    __tablename__ = "sites"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    base_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        back_populates="sites",
    )
