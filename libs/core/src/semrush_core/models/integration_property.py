"""
Integration property model for discovered provider properties.

Stores properties discovered from OAuth providers such as GSC sites,
GA4 properties, or BWT sites that can be mapped to projects.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.integration_account import IntegrationAccount
    from semrush_core.models.integration_mapping import IntegrationMapping


class IntegrationProperty(Base, UUIDMixin):
    """
    Integration property model for discovered provider properties.

    When a user connects an OAuth account, we discover their accessible
    properties (e.g., GSC sites, GA4 properties) and store them here.
    These properties can then be mapped to projects via IntegrationMapping.

    Attributes:
        integration_account_id: UUID of the parent integration account.
        provider: Provider type (e.g., 'google_search_console', 'google_analytics').
        property_id: External property ID from the provider.
        display_name: Human-readable name for the property.
        property_type: Provider-specific type (e.g., 'siteUrl' for GSC).
        metadata_: Additional provider-specific metadata.
        discovered_at: When this property was discovered.
        account: Parent integration account.
        mappings: Project mappings using this property.
    """

    __tablename__ = "integration_properties"

    __table_args__ = (
        UniqueConstraint(
            "integration_account_id",
            "provider",
            "property_id",
            name="uq_integration_properties_account_provider_property",
        ),
    )

    integration_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    property_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    property_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    account: Mapped["IntegrationAccount"] = relationship(
        back_populates="properties",
    )
    mappings: Mapped[list["IntegrationMapping"]] = relationship(
        back_populates="integration_property",
        cascade="all, delete-orphan",
    )

    @property
    def full_identifier(self) -> str:
        """
        Get a unique identifier string for this property.

        Returns:
            A string combining provider and property_id.
        """
        return f"{self.provider}:{self.property_id}"

    def is_gsc_property(self) -> bool:
        """Check if this is a Google Search Console property."""
        return self.provider == "google_search_console"

    def is_ga4_property(self) -> bool:
        """Check if this is a Google Analytics 4 property."""
        return self.provider == "google_analytics"

    def is_bwt_property(self) -> bool:
        """Check if this is a Bing Webmaster Tools property."""
        return self.provider == "bing_webmaster_tools"
