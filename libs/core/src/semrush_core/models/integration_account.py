"""
Integration account model for OAuth-linked third-party services.

Stores OAuth tokens and metadata for integrations like Google Search Console,
Google Analytics, Bing Webmaster Tools, etc.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.integration_property import IntegrationProperty
    from semrush_core.models.integration_token import IntegrationToken
    from semrush_core.models.user import User


class IntegrationProvider(str, Enum):
    """Supported integration providers."""

    GOOGLE_SEARCH_CONSOLE = "google_search_console"
    GOOGLE_ANALYTICS = "google_analytics"
    BING_WEBMASTER_TOOLS = "bing_webmaster_tools"


class IntegrationAccount(Base, UUIDMixin, TimestampMixin):
    """
    Integration account model for OAuth-connected third-party services.

    Stores OAuth credentials and metadata for external service integrations.
    Each user can have multiple integration accounts of different providers,
    but only one per provider (enforced by unique constraint).

    Attributes:
        user_id: UUID of the user who owns this integration.
        provider: Integration provider type (GSC, GA4, BWT).
        provider_account_id: External account ID from the provider.
        access_token_encrypted: Encrypted OAuth access token.
        refresh_token_encrypted: Encrypted OAuth refresh token.
        token_expires_at: When the access token expires.
        scopes: OAuth scopes granted.
        metadata: Additional provider-specific metadata.
        user: User who owns this integration.
    """

    __tablename__ = "integration_accounts"

    # Ensure one integration per provider per user
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "provider",
            name="uq_integration_accounts_user_provider",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    provider_account_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    access_token_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    refresh_token_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    scopes: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sync_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default="pending",
    )
    sync_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="integration_accounts",
    )
    token: Mapped["IntegrationToken | None"] = relationship(
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )
    properties: Mapped[list["IntegrationProperty"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )

    def is_token_expired(self) -> bool:
        """
        Check if the access token has expired.

        Returns:
            True if token is expired or expiry is unknown.
        """
        if self.token_expires_at is None:
            return True
        return datetime.now(self.token_expires_at.tzinfo) >= self.token_expires_at

    def needs_refresh(self, buffer_seconds: int = 300) -> bool:
        """
        Check if the token needs refreshing.

        Args:
            buffer_seconds: Seconds before expiry to trigger refresh.

        Returns:
            True if token should be refreshed.
        """
        if self.token_expires_at is None:
            return True
        from datetime import timedelta

        threshold = self.token_expires_at - timedelta(seconds=buffer_seconds)
        return datetime.now(self.token_expires_at.tzinfo) >= threshold
