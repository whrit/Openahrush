"""
Integration mapping model for linking properties to projects.

Maps discovered integration properties to projects, enabling
data sync from external providers to specific project contexts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.integration_property import IntegrationProperty
    from semrush_core.models.project import Project
    from semrush_core.models.site import Site
    from semrush_core.models.sync_run import SyncRun


class IntegrationMapping(Base, UUIDMixin):
    """
    Integration mapping model for linking properties to projects.

    Each mapping connects an integration property (e.g., a GSC site)
    to a project, optionally associating it with a specific site within
    the project. The is_primary flag indicates the main data source.

    Attributes:
        project_id: UUID of the project this mapping belongs to.
        site_id: Optional UUID of the specific site (for multi-site projects).
        integration_property_id: UUID of the integration property.
        is_primary: Whether this is the primary data source for the project.
        created_at: When this mapping was created.
        project: Parent project.
        site: Optional associated site.
        property: The integration property being mapped.
        sync_runs: Sync execution history for this mapping.
    """

    __tablename__ = "integration_mappings"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "integration_property_id",
            name="uq_integration_mappings_project_property",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="SET NULL"),
        nullable=True,
    )
    integration_property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_properties.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped[Project] = relationship()
    site: Mapped[Site | None] = relationship()
    integration_property: Mapped[IntegrationProperty] = relationship(
        back_populates="mappings",
    )
    sync_runs: Mapped[list[SyncRun]] = relationship(
        back_populates="mapping",
        cascade="all, delete-orphan",
        order_by="desc(SyncRun.created_at)",
    )

    @property
    def latest_sync(self) -> SyncRun | None:
        """
        Get the most recent sync run for this mapping.

        Returns:
            The latest SyncRun or None if no syncs have run.
        """
        if self.sync_runs:
            return self.sync_runs[0]
        return None

    @property
    def is_syncing(self) -> bool:
        """
        Check if a sync is currently in progress.

        Returns:
            True if there's an active sync run.
        """
        latest = self.latest_sync
        return latest is not None and latest.status in ("queued", "running")

    def get_sync_status(self) -> str:
        """
        Get the current sync status.

        Returns:
            Status string ('never', 'queued', 'running', 'completed', 'failed').
        """
        latest = self.latest_sync
        if latest is None:
            return "never"
        return latest.status
