"""
Token service for managing OAuth tokens with encryption.

Provides secure storage, retrieval, and automatic refresh of OAuth tokens
for integration accounts. Includes both sync and async implementations.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from semrush_core.models.integration_token import IntegrationToken
from semrush_core.security.encryption import decrypt_token, encrypt_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from semrush_integrations.oauth.base import OAuthProvider, OAuthTokens


class AsyncTokenService:
    """
    Async service for managing OAuth tokens with encryption.

    Handles secure storage, retrieval, and automatic refresh of OAuth tokens
    for integration accounts. All tokens are encrypted at rest using Fernet
    symmetric encryption.

    This is the preferred service for use in async contexts (FastAPI routes,
    async workers, etc.) as it properly awaits async operations.

    Example:
        >>> service = AsyncTokenService(db_session)
        >>> await service.store_tokens(account_id, oauth_tokens)
        >>> token = await service.get_valid_token(account_id, provider)
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize async token service.

        Args:
            db: Async SQLAlchemy session for database operations.
        """
        self.db = db

    async def store_tokens(self, account_id: UUID, tokens: OAuthTokens) -> IntegrationToken:
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
        result = await self.db.execute(
            select(IntegrationToken).where(
                IntegrationToken.integration_account_id == account_id
            )
        )
        existing = result.scalar_one_or_none()

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

        await self.db.commit()
        await self.db.refresh(token)
        return token

    async def get_valid_token(
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
        result = await self.db.execute(
            select(IntegrationToken).where(
                IntegrationToken.integration_account_id == account_id
            )
        )
        token = result.scalar_one_or_none()

        if not token:
            raise ValueError(f"No token found for account {account_id}")

        # Check if token needs refresh (within buffer period of expiry)
        needs_refresh = False
        if token.expires_at is not None:
            # Ensure timezone-aware comparison
            now = datetime.now(UTC)
            expires_at = token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)

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

            # Properly await async refresh
            new_tokens = await provider.refresh_tokens(refresh_token)
            await self.store_tokens(account_id, new_tokens)
            return new_tokens.access_token

        return self.decrypt_access_token(token)

    async def revoke_tokens(self, account_id: UUID, provider: OAuthProvider) -> bool:
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
        result = await self.db.execute(
            select(IntegrationToken).where(
                IntegrationToken.integration_account_id == account_id
            )
        )
        token = result.scalar_one_or_none()

        if not token:
            return False

        # Decrypt and revoke the access token
        access_token = self.decrypt_access_token(token)
        await provider.revoke_token(access_token)

        # Delete the token record
        await self.db.delete(token)
        await self.db.commit()
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


class TokenService:
    """
    Synchronous service for managing OAuth tokens with encryption.

    .. deprecated::
        Use :class:`AsyncTokenService` instead for async contexts.
        This class uses thread pool execution for async provider calls,
        which may have performance implications.

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
        import warnings

        warnings.warn(
            "TokenService is deprecated. Use AsyncTokenService for async contexts.",
            DeprecationWarning,
            stacklevel=2,
        )
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
            now = datetime.now(UTC)
            expires_at = token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)

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

            # Run async refresh in sync context using thread-safe approach
            import asyncio
            import concurrent.futures

            def _run_async():
                return asyncio.run(provider.refresh_tokens(refresh_token))

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_run_async)
                new_tokens = future.result()

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

        # Decrypt and revoke the access token using thread-safe approach
        import asyncio
        import concurrent.futures

        access_token = self.decrypt_access_token(token)

        def _run_async():
            return asyncio.run(provider.revoke_token(access_token))

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_run_async)
            future.result()  # Wait for completion

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
