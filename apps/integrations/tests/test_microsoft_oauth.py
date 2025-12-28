"""
Tests for Microsoft OAuth provider.

Following TDD: These tests are written FIRST, then the implementation.
Uses respx to mock HTTP requests.
"""

from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx
import pytest
import respx
from semrush_integrations.oauth.base import OAuthTokens, OAuthUserInfo
from semrush_integrations.oauth.microsoft import MicrosoftOAuthProvider


class TestMicrosoftOAuthProviderAttributes:
    """Tests for Microsoft OAuth provider class attributes."""

    def test_provider_name(self):
        """Provider name should be 'microsoft'."""
        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert provider.provider_name == "microsoft"

    def test_authorization_url(self):
        """Should use Microsoft's OAuth authorization URL."""
        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert "login.microsoftonline.com" in provider.authorization_url
        assert "/oauth2/v2.0/authorize" in provider.authorization_url

    def test_token_url(self):
        """Should use Microsoft's OAuth token URL."""
        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert "login.microsoftonline.com" in provider.token_url
        assert "/oauth2/v2.0/token" in provider.token_url

    def test_default_scopes_include_openid(self):
        """Default scopes should include OpenID Connect."""
        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert "openid" in provider.scopes

    def test_default_scopes_include_email(self):
        """Default scopes should include email."""
        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert "email" in provider.scopes

    def test_default_scopes_include_offline_access(self):
        """Default scopes should include offline_access for refresh tokens."""
        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert "offline_access" in provider.scopes


class TestMicrosoftOAuthProviderAuthorizationUrl:
    """Tests for Microsoft OAuth authorization URL generation."""

    def test_authorization_url_uses_microsoft_endpoint(self):
        """Authorization URL should use Microsoft's endpoint."""
        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        url = provider.get_authorization_url("test_state")
        parsed = urlparse(url)
        assert parsed.netloc == "login.microsoftonline.com"


class TestMicrosoftOAuthProviderExchangeCode:
    """Tests for Microsoft OAuth code exchange."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_makes_post_request(self):
        """exchange_code should make POST request to token URL."""
        respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "eyJ0eXAi.test_access_token",
                    "refresh_token": "OAAABAAAAi.test_refresh_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid email",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        await provider.exchange_code("auth_code_123")

        assert respx.calls.last is not None
        assert respx.calls.last.request.method == "POST"

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_returns_oauth_tokens(self):
        """exchange_code should return OAuthTokens."""
        respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "eyJ0eXAi.test_access_token",
                    "refresh_token": "OAAABAAAAi.test_refresh_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid email",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        tokens = await provider.exchange_code("auth_code_123")

        assert isinstance(tokens, OAuthTokens)
        assert tokens.access_token == "eyJ0eXAi.test_access_token"
        assert tokens.refresh_token == "OAAABAAAAi.test_refresh_token"
        assert tokens.token_type == "Bearer"

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_calculates_expires_at(self):
        """exchange_code should calculate expires_at from expires_in."""
        respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "eyJ0eXAi.test_access_token",
                    "refresh_token": "OAAABAAAAi.test_refresh_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid email",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        before = datetime.utcnow()
        tokens = await provider.exchange_code("auth_code_123")
        after = datetime.utcnow()

        assert tokens.expires_at is not None
        expected_min = before + timedelta(seconds=3600)
        expected_max = after + timedelta(seconds=3600)
        assert expected_min <= tokens.expires_at <= expected_max

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_parses_scopes(self):
        """exchange_code should parse space-separated scopes."""
        respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "eyJ0eXAi.test",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid email profile",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        tokens = await provider.exchange_code("auth_code_123")

        assert tokens.scopes == ["openid", "email", "profile"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_sends_correct_parameters(self):
        """exchange_code should send required parameters."""
        respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "eyJ0eXAi.test",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="my_client_id",
            client_secret="my_client_secret",
            redirect_uri="https://app.example.com/callback",
        )
        await provider.exchange_code("my_auth_code")

        request = respx.calls.last.request
        body = request.content.decode()
        params = dict(pair.split("=") for pair in body.split("&"))

        assert params["client_id"] == "my_client_id"
        assert params["client_secret"] == "my_client_secret"
        assert params["code"] == "my_auth_code"
        assert params["grant_type"] == "authorization_code"

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_raises_on_error(self):
        """exchange_code should raise HTTPStatusError on failure."""
        respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
            return_value=httpx.Response(
                400,
                json={"error": "invalid_grant"},
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )

        with pytest.raises(httpx.HTTPStatusError):
            await provider.exchange_code("invalid_code")


class TestMicrosoftOAuthProviderRefreshTokens:
    """Tests for Microsoft OAuth token refresh."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_tokens_makes_post_request(self):
        """refresh_tokens should make POST request to token URL."""
        respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "eyJ0eXAi.new_access_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid email",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        await provider.refresh_tokens("refresh_token_123")

        assert respx.calls.last.request.method == "POST"

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_tokens_returns_new_tokens(self):
        """refresh_tokens should return new OAuthTokens."""
        respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "eyJ0eXAi.new_access_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid email",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        tokens = await provider.refresh_tokens("refresh_token_123")

        assert isinstance(tokens, OAuthTokens)
        assert tokens.access_token == "eyJ0eXAi.new_access_token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_tokens_preserves_refresh_token(self):
        """refresh_tokens should preserve original refresh token if not returned."""
        respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "eyJ0eXAi.new_access",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        tokens = await provider.refresh_tokens("original_refresh_token")

        assert tokens.refresh_token == "original_refresh_token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_tokens_sends_correct_grant_type(self):
        """refresh_tokens should send refresh_token grant type."""
        respx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "eyJ0eXAi.test",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        await provider.refresh_tokens("refresh_token_123")

        request = respx.calls.last.request
        body = request.content.decode()
        assert "grant_type=refresh_token" in body


class TestMicrosoftOAuthProviderUserInfo:
    """Tests for Microsoft OAuth user info retrieval."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user_info_makes_get_request(self):
        """get_user_info should make GET request to MS Graph userinfo URL."""
        respx.get("https://graph.microsoft.com/v1.0/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "abc-123-def-456",
                    "mail": "user@outlook.com",
                    "displayName": "Test User",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        await provider.get_user_info("access_token_123")

        assert respx.calls.last.request.method == "GET"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user_info_returns_oauth_user_info(self):
        """get_user_info should return OAuthUserInfo."""
        respx.get("https://graph.microsoft.com/v1.0/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "abc-123-def-456",
                    "mail": "user@outlook.com",
                    "displayName": "Test User",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        user = await provider.get_user_info("access_token_123")

        assert isinstance(user, OAuthUserInfo)
        assert user.external_id == "abc-123-def-456"
        assert user.email == "user@outlook.com"
        assert user.name == "Test User"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user_info_sends_authorization_header(self):
        """get_user_info should send Bearer token in Authorization header."""
        respx.get("https://graph.microsoft.com/v1.0/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "abc-123-def-456",
                    "mail": "user@outlook.com",
                    "displayName": "Test User",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        await provider.get_user_info("my_access_token")

        request = respx.calls.last.request
        assert request.headers["Authorization"] == "Bearer my_access_token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user_info_handles_missing_optional_fields(self):
        """get_user_info should handle missing email and name."""
        respx.get("https://graph.microsoft.com/v1.0/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "abc-123-def-456",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        user = await provider.get_user_info("access_token_123")

        assert user.external_id == "abc-123-def-456"
        assert user.email is None
        assert user.name is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user_info_uses_userPrincipalName_as_email_fallback(self):
        """get_user_info should fall back to userPrincipalName for email."""
        respx.get("https://graph.microsoft.com/v1.0/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "abc-123-def-456",
                    "userPrincipalName": "user@company.onmicrosoft.com",
                    "displayName": "Test User",
                },
            )
        )

        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        user = await provider.get_user_info("access_token_123")

        assert user.email == "user@company.onmicrosoft.com"


class TestMicrosoftOAuthProviderRevokeToken:
    """Tests for Microsoft OAuth token revocation."""

    @pytest.mark.asyncio
    async def test_revoke_token_returns_true(self):
        """revoke_token should return True (MS doesn't support revocation via API)."""
        provider = MicrosoftOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        result = await provider.revoke_token("token_to_revoke")

        # Microsoft doesn't have a public token revocation endpoint
        # The token will expire naturally or be revoked via Azure portal
        assert result is True
