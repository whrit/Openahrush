"""
Token service for managing OAuth tokens with encryption.

Provides secure storage, retrieval, and automatic refresh of OAuth tokens
for integration accounts.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from semrush_core.models.integration_token import IntegrationToken
from semrush_core.security.encryption import decrypt_token, encrypt_token
from semrush_integrations.oauth.base import OAuthProvider, OAuthTokens


class TokenService:
    """
    Service for managing OAuth tokens with encryption.

    Handles secure storage, retrieval, and automatic refresh of OAuth tokens
    for integration accounts. All tokens are encrypted at rest using Fernet
    symmetric encryption.

    Example:
        >>> service = TokenService(db_session)
        >>> service.store_tokens(account_id, oauth_tokens)
        >>> token = service.get_valid_token(account_id, provider)
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize token service.

        Args:
            db: SQLAlchemy session for database operations.
        """
        self.db = db

    def store_tokens(self, account_id: UUID, tokens: OAuthTokens) -> IntegrationToken:
        """
        Store encrypted tokens for an integration account.

        Creates a new token record or updates an existing one. Tokens are
        encrypted before storage using Fernet encryption.

        Args:
            account_id: UUID of the integration account.
            tokens: OAuthTokens containing access and refresh tokens.

        Returns:
            The created or updated IntegrationToken record.
        """
        # Check for existing token
        existing = self.db.query(IntegrationToken).filter(
            IntegrationToken.integration_account_id == account_id
        ).first()

        # Encrypt tokens
        encrypted_access = encrypt_token(tokens.access_token)
        encrypted_refresh = None
        if tokens.refresh_token is not None:
            encrypted_refresh = encrypt_token(tokens.refresh_token)

        # Convert encrypted strings to bytes for LargeBinary column
        access_bytes = encrypted_access.encode("utf-8")
        refresh_bytes = encrypted_refresh.encode("utf-8") if encrypted_refresh else None

        if existing:
            existing.access_token_encrypted = access_bytes
            existing.refresh_token_encrypted = refresh_bytes
            existing.token_type = tokens.token_type
            existing.expires_at = tokens.expires_at
            existing.scopes = tokens.scopes
            token = existing
        else:
            token = IntegrationToken(
                integration_account_id=account_id,
                access_token_encrypted=access_bytes,
                refresh_token_encrypted=refresh_bytes,
                token_type=tokens.token_type,
                expires_at=tokens.expires_at,
                scopes=tokens.scopes,
            )
            self.db.add(token)

        self.db.commit()
        self.db.refresh(token)
        return token

    def get_valid_token(
        self,
        account_id: UUID,
        provider: OAuthProvider,
        buffer_minutes: int = 5,
    ) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Retrieves the access token for an account. If the token is expired
        or within the buffer period of expiry, automatically refreshes it
        using the refresh token and provider.

        Args:
            account_id: UUID of the integration account.
            provider: OAuthProvider instance for token refresh.
            buffer_minutes: Minutes before expiry to trigger refresh.

        Returns:
            Decrypted access token string.

        Raises:
            ValueError: If no token exists or token is expired without refresh token.
        """
        token = self.db.query(IntegrationToken).filter(
            IntegrationToken.integration_account_id == account_id
        ).first()

        if not token:
            raise ValueError(f"No token found for account {account_id}")

        # Check if token needs refresh (within buffer period of expiry)
        needs_refresh = False
        if token.expires_at is not None:
            # Ensure timezone-aware comparison
            now = datetime.now(timezone.utc)
            expires_at = token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            buffer = timedelta(minutes=buffer_minutes)
            if now >= expires_at - buffer:
                needs_refresh = True

        if needs_refresh:
            if not token.refresh_token_encrypted:
                raise ValueError("Token expired and no refresh token available")

            # Decrypt refresh token and get new tokens
            refresh_token = self.decrypt_refresh_token(token)
            if refresh_token is None:
                raise ValueError("Token expired and no refresh token available")

            # Run async refresh in sync context
            new_tokens = asyncio.get_event_loop().run_until_complete(
                provider.refresh_tokens(refresh_token)
            )
            self.store_tokens(account_id, new_tokens)
            return new_tokens.access_token

        return self.decrypt_access_token(token)

    def revoke_tokens(self, account_id: UUID, provider: OAuthProvider) -> bool:
        """
        Revoke and delete tokens for an account.

        Calls the provider's revoke endpoint and removes the token record
        from the database.

        Args:
            account_id: UUID of the integration account.
            provider: OAuthProvider instance for token revocation.

        Returns:
            True if tokens were revoked and deleted, False if no token existed.
        """
        token = self.db.query(IntegrationToken).filter(
            IntegrationToken.integration_account_id == account_id
        ).first()

        if not token:
            return False

        # Decrypt and revoke the access token
        access_token = self.decrypt_access_token(token)
        asyncio.get_event_loop().run_until_complete(
            provider.revoke_token(access_token)
        )

        # Delete the token record
        self.db.delete(token)
        self.db.commit()
        return True

    def decrypt_access_token(self, token: IntegrationToken) -> str:
        """
        Decrypt the access token from an IntegrationToken record.

        Args:
            token: IntegrationToken record with encrypted token.

        Returns:
            Decrypted access token string.
        """
        encrypted = token.access_token_encrypted.decode("utf-8")
        return decrypt_token(encrypted)

    def decrypt_refresh_token(self, token: IntegrationToken) -> str | None:
        """
        Decrypt the refresh token from an IntegrationToken record.

        Args:
            token: IntegrationToken record with encrypted token.

        Returns:
            Decrypted refresh token string or None if not present.
        """
        if token.refresh_token_encrypted is None:
            return None
        encrypted = token.refresh_token_encrypted.decode("utf-8")
        return decrypt_token(encrypted)
