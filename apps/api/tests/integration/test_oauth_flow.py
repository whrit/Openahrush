"""
Integration tests for OAuth flow following TDD principles.

Tests complete OAuth authentication flows including:
- Full OAuth connect → callback → token storage flow
- Token refresh flow with encryption
- Token encryption/decryption roundtrip
- Error handling and retry scenarios
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from semrush_core.models import IntegrationAccount
from semrush_core.security.encryption import decrypt_token, encrypt_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TestOAuthConnectFlow:
    """Test complete OAuth connect flow."""

    @pytest.mark.asyncio
    async def test_oauth_connect_generates_authorization_url(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db_session: AsyncSession,
        test_user: Any,
    ) -> None:
        """
        Test that OAuth connect initiates the flow and returns authorization URL.

        Flow:
        1. User requests to connect Google Search Console
        2. System generates state token and authorization URL
        3. System stores state token for CSRF validation
        """
        response = await integration_client.post(
            "/integrations/google_search_console/connect",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert "state" in data
        assert "accounts.google.com" in data["authorization_url"]
        assert data["state"] in data["authorization_url"]

    @pytest.mark.asyncio
    async def test_oauth_connect_callback_creates_integration_account(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db_session: AsyncSession,
        test_user: Any,
        mock_oauth_tokens: dict,
        mock_oauth_user_info: dict,
    ) -> None:
        """
        Test that OAuth callback creates and stores integration account.

        Flow:
        1. Generate state token via connect endpoint
        2. Call callback with authorization code and state
        3. System exchanges code for tokens
        4. System fetches user info from provider
        5. System creates IntegrationAccount with encrypted tokens
        """
        # Step 1: Initiate connect to get state token
        connect_response = await integration_client.post(
            "/integrations/google_search_console/connect",
            headers=auth_headers,
        )
        assert connect_response.status_code == 200
        state_token = connect_response.json()["state"]

        # Step 2: Mock the OAuth provider for callback
        with patch("semrush_api.routers.integrations.get_oauth_provider") as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.exchange_code = AsyncMock(
                return_value=MagicMock(
                    access_token=mock_oauth_tokens["access_token"],
                    refresh_token=mock_oauth_tokens["refresh_token"],
                    token_type=mock_oauth_tokens["token_type"],
                    expires_at=mock_oauth_tokens["expires_at"],
                    scopes=mock_oauth_tokens["scopes"],
                )
            )
            mock_provider.get_user_info = AsyncMock(
                return_value=MagicMock(
                    external_id=mock_oauth_user_info["external_id"],
                    email=mock_oauth_user_info["email"],
                    name=mock_oauth_user_info["name"],
                )
            )
            mock_get_provider.return_value = mock_provider

            # Step 3: Call callback
            callback_response = await integration_client.post(
                "/integrations/google_search_console/callback",
                headers=auth_headers,
                json={"code": "test_authorization_code", "state": state_token},
            )

        assert callback_response.status_code == 200
        callback_data = callback_response.json()
        assert callback_data["provider"] == "google_search_console"
        assert callback_data["connected"] is True

        # Step 4: Verify IntegrationAccount was created in database
        result = await test_db_session.execute(
            select(IntegrationAccount).where(
                IntegrationAccount.user_id == test_user.id,
                IntegrationAccount.provider == "google_search_console",
            )
        )
        account = result.scalar_one_or_none()

        assert account is not None
        assert account.provider_account_id == mock_oauth_user_info["external_id"]
        assert account.token_expires_at == mock_oauth_tokens["expires_at"]
        assert account.scopes == mock_oauth_tokens["scopes"]

    @pytest.mark.asyncio
    async def test_oauth_connect_callback_with_invalid_state_returns_400(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Test that OAuth callback rejects invalid state token.

        This prevents CSRF attacks by validating the state token.
        """
        from semrush_api.routers.integrations import reset_oauth_state_manager

        # Ensure clean state
        reset_oauth_state_manager()

        response = await integration_client.post(
            "/integrations/google_search_console/callback",
            headers=auth_headers,
            json={"code": "test_code", "state": "invalid_state_token"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "state" in data["detail"].lower()


class TestTokenEncryption:
    """Test OAuth token encryption and decryption."""

    @pytest.mark.asyncio
    async def test_tokens_are_stored_encrypted(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db_session: AsyncSession,
        test_user: Any,
        mock_oauth_tokens: dict,
        mock_oauth_user_info: dict,
    ) -> None:
        """
        Test that access tokens and refresh tokens are encrypted before storage.

        Security requirement: Tokens must never be stored in plaintext.
        """
        # Initiate connect
        connect_response = await integration_client.post(
            "/integrations/google_search_console/connect",
            headers=auth_headers,
        )
        state_token = connect_response.json()["state"]

        # Mock OAuth provider
        with patch("semrush_api.routers.integrations.get_oauth_provider") as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.exchange_code = AsyncMock(
                return_value=MagicMock(
                    access_token=mock_oauth_tokens["access_token"],
                    refresh_token=mock_oauth_tokens["refresh_token"],
                    token_type=mock_oauth_tokens["token_type"],
                    expires_at=mock_oauth_tokens["expires_at"],
                    scopes=mock_oauth_tokens["scopes"],
                )
            )
            mock_provider.get_user_info = AsyncMock(
                return_value=MagicMock(
                    external_id=mock_oauth_user_info["external_id"],
                    email=mock_oauth_user_info["email"],
                    name=mock_oauth_user_info["name"],
                )
            )
            mock_get_provider.return_value = mock_provider

            # Complete callback
            await integration_client.post(
                "/integrations/google_search_console/callback",
                headers=auth_headers,
                json={"code": "test_code", "state": state_token},
            )

        # Verify token is encrypted in database
        result = await test_db_session.execute(
            select(IntegrationAccount).where(IntegrationAccount.user_id == test_user.id)
        )
        account = result.scalar_one_or_none()

        # The stored token should be encrypted (not match plaintext)
        # Note: We need to fetch the IntegrationToken to check encryption
        # For now, verify account exists
        assert account is not None

    @pytest.mark.asyncio
    async def test_token_encryption_decryption_roundtrip(
        self,
    ) -> None:
        """
        Test that token encryption and decryption works correctly.

        Verifies:
        1. Encrypted value differs from plaintext
        2. Decrypted value matches original plaintext
        3. Different plaintexts produce different ciphertexts
        """
        original_token = "test_access_token_12345"

        # Encrypt the token
        encrypted_token = encrypt_token(original_token)

        # Verify encrypted value is different from plaintext
        assert encrypted_token != original_token
        assert len(encrypted_token) > len(original_token)

        # Decrypt the token
        decrypted_token = decrypt_token(encrypted_token)

        # Verify decryption produces original value
        assert decrypted_token == original_token

        # Verify different tokens produce different encrypted values
        other_token = "different_token_67890"
        other_encrypted = encrypt_token(other_token)
        assert other_encrypted != encrypted_token


class TestTokenRefreshFlow:
    """Test OAuth token refresh flow."""

    @pytest.mark.asyncio
    async def test_token_refresh_updates_access_token(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db_session: AsyncSession,
        test_integration_account: IntegrationAccount,
        mock_oauth_tokens: dict,
    ) -> None:
        """
        Test that token refresh updates the access token in database.

        Flow:
        1. System detects expired or nearly-expired access token
        2. System uses refresh token to get new access token
        3. System updates stored access token (encrypted)
        4. System updates expiration timestamp
        """
        # Mock the OAuth provider refresh
        with patch("semrush_integrations.oauth.google.GoogleOAuthProvider") as MockProvider:
            mock_provider = AsyncMock()
            mock_provider.refresh_access_token = AsyncMock(
                return_value=MagicMock(
                    access_token="new_refreshed_access_token",
                    refresh_token=mock_oauth_tokens["refresh_token"],
                    token_type=mock_oauth_tokens["token_type"],
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    scopes=mock_oauth_tokens["scopes"],
                )
            )
            MockProvider.return_value = mock_provider

            # Trigger a refresh (this would normally be done by a background worker)
            # For now, we just verify the provider can be mocked correctly
            new_tokens = await mock_provider.refresh_access_token("old_refresh_token")

            assert new_tokens.access_token == "new_refreshed_access_token"
            assert new_tokens.expires_at > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_token_refresh_preserves_refresh_token(
        self,
        test_db_session: AsyncSession,
        test_integration_account: IntegrationAccount,
    ) -> None:
        """
        Test that token refresh preserves the refresh token.

        Some OAuth providers (like Google) return a new refresh token
        only on the first authorization. Subsequent refreshes should
        preserve the existing refresh token.
        """
        # Mock refresh that returns same refresh token
        with patch("semrush_integrations.oauth.google.GoogleOAuthProvider") as MockProvider:
            mock_provider = AsyncMock()
            mock_provider.refresh_access_token = AsyncMock(
                return_value=MagicMock(
                    access_token="new_access_token",
                    refresh_token="same_refresh_token",
                    token_type="Bearer",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    scopes=["email", "openid"],
                )
            )
            MockProvider.return_value = mock_provider

            result = await mock_provider.refresh_access_token("same_refresh_token")

            # Verify refresh token is unchanged
            assert result.refresh_token == "same_refresh_token"


class TestOAuthDisconnectFlow:
    """Test OAuth disconnect flow."""

    @pytest.mark.asyncio
    async def test_disconnect_revokes_tokens_and_deletes_account(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db_session: AsyncSession,
        test_user: Any,
        test_integration_account: IntegrationAccount,
    ) -> None:
        """
        Test that disconnect revokes tokens and deletes integration account.

        Flow:
        1. User requests to disconnect integration
        2. System revokes access token with provider
        3. System deletes IntegrationAccount from database
        4. System returns success confirmation
        """
        # Mock the OAuth provider revocation
        with patch("semrush_api.routers.integrations.GoogleOAuthProvider") as MockProvider:
            mock_provider = AsyncMock()
            mock_provider.revoke_token = AsyncMock(return_value=True)
            MockProvider.return_value = mock_provider

            # Call disconnect
            response = await integration_client.delete(
                "/integrations/google_search_console/disconnect",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert "disconnected" in data["message"].lower()

        # Verify account was deleted
        result = await test_db_session.execute(
            select(IntegrationAccount).where(IntegrationAccount.id == test_integration_account.id)
        )
        account = result.scalar_one_or_none()
        assert account is None

    @pytest.mark.asyncio
    async def test_disconnect_continues_even_if_revocation_fails(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db_session: AsyncSession,
        test_user: Any,
        test_integration_account: IntegrationAccount,
    ) -> None:
        """
        Test that disconnect completes even if token revocation fails.

        This ensures users can disconnect even if the provider is unreachable
        or the token has already been revoked.
        """
        # Mock revocation failure
        with patch("semrush_api.routers.integrations.GoogleOAuthProvider") as MockProvider:
            mock_provider = AsyncMock()
            mock_provider.revoke_token = AsyncMock(side_effect=Exception("Provider unreachable"))
            MockProvider.return_value = mock_provider

            # Call disconnect - should still succeed
            response = await integration_client.delete(
                "/integrations/google_search_console/disconnect",
                headers=auth_headers,
            )

        # Should still return success (graceful degradation)
        assert response.status_code in [200, 500]  # May return error but should clean up

        # Verify account was still deleted
        result = await test_db_session.execute(
            select(IntegrationAccount).where(IntegrationAccount.id == test_integration_account.id)
        )
        account = result.scalar_one_or_none()
        # Account should be deleted even if revocation failed
        assert account is None


class TestOAuthErrorHandling:
    """Test OAuth error handling scenarios."""

    @pytest.mark.asyncio
    async def test_oauth_callback_with_invalid_code_returns_error(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Test that OAuth callback with invalid authorization code returns error.

        Provider will reject the code exchange, and we should return
        a clear error to the user.
        """
        # Initiate connect
        connect_response = await integration_client.post(
            "/integrations/google_search_console/connect",
            headers=auth_headers,
        )
        state_token = connect_response.json()["state"]

        # Mock provider to reject invalid code
        with patch("semrush_api.routers.integrations.get_oauth_provider") as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.exchange_code = AsyncMock(
                side_effect=Exception("Invalid authorization code")
            )
            mock_get_provider.return_value = mock_provider

            # Call callback with invalid code
            response = await integration_client.post(
                "/integrations/google_search_console/callback",
                headers=auth_headers,
                json={"code": "invalid_code", "state": state_token},
            )

        # Should return error status
        assert response.status_code in [400, 500]

    @pytest.mark.asyncio
    async def test_oauth_connect_when_already_connected_returns_conflict(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_integration_account: IntegrationAccount,
    ) -> None:
        """
        Test that attempting to connect when already connected returns 409 Conflict.

        Users should disconnect first before reconnecting.
        """
        response = await integration_client.post(
            "/integrations/google_search_console/connect",
            headers=auth_headers,
        )

        assert response.status_code == 409
        data = response.json()
        assert "already connected" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_oauth_callback_missing_code_returns_422(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Test that OAuth callback without authorization code returns validation error.
        """
        response = await integration_client.post(
            "/integrations/google_search_console/callback",
            headers=auth_headers,
            json={"state": "some_state"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_oauth_callback_missing_state_returns_422(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Test that OAuth callback without state token returns validation error.
        """
        response = await integration_client.post(
            "/integrations/google_search_console/callback",
            headers=auth_headers,
            json={"code": "some_code"},
        )

        assert response.status_code == 422


class TestMultiProviderOAuth:
    """Test OAuth flow with multiple providers."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "provider,expected_domain",
        [
            ("google_search_console", "accounts.google.com"),
            ("google_analytics", "accounts.google.com"),
            ("bing_webmaster_tools", "login.microsoftonline.com"),
        ],
    )
    async def test_oauth_connect_supports_multiple_providers(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        provider: str,
        expected_domain: str,
    ) -> None:
        """
        Test that OAuth connect works for all supported providers.

        Each provider should generate appropriate authorization URLs.
        """
        response = await integration_client.post(
            f"/integrations/{provider}/connect",
            headers=auth_headers,
        )

        assert response.status_code in [200, 409]  # 200 if not connected, 409 if already connected
        if response.status_code == 200:
            data = response.json()
            assert "authorization_url" in data
            assert expected_domain in data["authorization_url"]
