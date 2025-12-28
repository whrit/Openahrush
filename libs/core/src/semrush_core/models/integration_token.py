"""
Integration token model for secure OAuth token storage.

Stores encrypted OAuth tokens separately from integration accounts
for enhanced security isolation and easier token rotation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.integration_account import IntegrationAccount


class IntegrationToken(Base, UUIDMixin, TimestampMixin):
    """
    Integration token model for secure OAuth token storage.

    Separates token storage from integration account metadata for:
    - Security isolation (tokens can be encrypted at rest)
    - Easier token rotation without affecting account state
    - Better audit trail for token operations

    Attributes:
        integration_account_id: UUID of the parent integration account.
        access_token_encrypted: Encrypted OAuth access token (binary).
        refresh_token_encrypted: Encrypted OAuth refresh token (binary).
        token_type: Token type (usually "Bearer").
        expires_at: When the access token expires.
        scopes: OAuth scopes granted for this token.
        account: Parent integration account relationship.
    """

    __tablename__ = "integration_tokens"

    integration_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    access_token_encrypted: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )
    refresh_token_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    token_type: Mapped[str] = mapped_column(
        String(50),
        default="Bearer",
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    scopes: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )

    # Relationships
    account: Mapped[IntegrationAccount] = relationship(
        back_populates="token",
    )

    def is_expired(self) -> bool:
        """
        Check if the access token has expired.

        Returns:
            True if token is expired or expiry is unknown.
        """
        if self.expires_at is None:
            return True
        return datetime.now(self.expires_at.tzinfo) >= self.expires_at

    def needs_refresh(self, buffer_seconds: int = 300) -> bool:
        """
        Check if the token needs refreshing.

        Args:
            buffer_seconds: Seconds before expiry to trigger refresh (default 5 min).

        Returns:
            True if token should be refreshed.
        """
        if self.expires_at is None:
            return True
        from datetime import timedelta

        threshold = self.expires_at - timedelta(seconds=buffer_seconds)
        return datetime.now(self.expires_at.tzinfo) >= threshold

    def has_scope(self, scope: str) -> bool:
        """
        Check if the token has a specific scope.

        Args:
            scope: The OAuth scope to check.

        Returns:
            True if the scope is present.
        """
        if self.scopes is None:
            return False
        return scope in self.scopes
