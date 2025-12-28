"""
Tests for Google OAuth provider.

Following TDD: These tests are written FIRST, then the implementation.
Uses respx to mock HTTP requests.
"""

import pytest
import respx
import httpx
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from semrush_integrations.oauth.google import GoogleOAuthProvider
from semrush_integrations.oauth.base import OAuthTokens, OAuthUserInfo


class TestGoogleOAuthProviderAttributes:
    """Tests for Google OAuth provider class attributes."""

    def test_provider_name(self):
        """Provider name should be 'google'."""
        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert provider.provider_name == "google"

    def test_authorization_url(self):
        """Should use Google's OAuth authorization URL."""
        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert provider.authorization_url == "https://accounts.google.com/o/oauth2/v2/auth"

    def test_token_url(self):
        """Should use Google's OAuth token URL."""
        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert provider.token_url == "https://oauth2.googleapis.com/token"

    def test_default_scopes_include_openid(self):
        """Default scopes should include OpenID Connect."""
        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert "openid" in provider.scopes

    def test_default_scopes_include_email(self):
        """Default scopes should include email."""
        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert "email" in provider.scopes

    def test_default_scopes_include_search_console(self):
        """Default scopes should include Google Search Console readonly."""
        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert "https://www.googleapis.com/auth/webmasters.readonly" in provider.scopes

    def test_default_scopes_include_analytics(self):
        """Default scopes should include Google Analytics readonly."""
        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        assert "https://www.googleapis.com/auth/analytics.readonly" in provider.scopes


class TestGoogleOAuthProviderAuthorizationUrl:
    """Tests for Google OAuth authorization URL generation."""

    def test_authorization_url_uses_google_endpoint(self):
        """Authorization URL should use Google's endpoint."""
        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        url = provider.get_authorization_url("test_state")
        parsed = urlparse(url)
        assert parsed.netloc == "accounts.google.com"
        assert parsed.path == "/o/oauth2/v2/auth"


class TestGoogleOAuthProviderExchangeCode:
    """Tests for Google OAuth code exchange."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_makes_post_request(self):
        """exchange_code should make POST request to token URL."""
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "ya29.test_access_token",
                    "refresh_token": "1//test_refresh_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid email",
                },
            )
        )

        provider = GoogleOAuthProvider(
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
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "ya29.test_access_token",
                    "refresh_token": "1//test_refresh_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid email",
                },
            )
        )

        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        tokens = await provider.exchange_code("auth_code_123")

        assert isinstance(tokens, OAuthTokens)
        assert tokens.access_token == "ya29.test_access_token"
        assert tokens.refresh_token == "1//test_refresh_token"
        assert tokens.token_type == "Bearer"

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_calculates_expires_at(self):
        """exchange_code should calculate expires_at from expires_in."""
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "ya29.test_access_token",
                    "refresh_token": "1//test_refresh_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid email",
                },
            )
        )

        provider = GoogleOAuthProvider(
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
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "ya29.test",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid email profile",
                },
            )
        )

        provider = GoogleOAuthProvider(
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
        route = respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "ya29.test",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid",
                },
            )
        )

        provider = GoogleOAuthProvider(
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
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                400,
                json={"error": "invalid_grant"},
            )
        )

        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )

        with pytest.raises(httpx.HTTPStatusError):
            await provider.exchange_code("invalid_code")


class TestGoogleOAuthProviderRefreshTokens:
    """Tests for Google OAuth token refresh."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_tokens_makes_post_request(self):
        """refresh_tokens should make POST request to token URL."""
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "ya29.new_access_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid email",
                },
            )
        )

        provider = GoogleOAuthProvider(
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
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "ya29.new_access_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid email",
                },
            )
        )

        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        tokens = await provider.refresh_tokens("refresh_token_123")

        assert isinstance(tokens, OAuthTokens)
        assert tokens.access_token == "ya29.new_access_token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_tokens_preserves_refresh_token(self):
        """refresh_tokens should preserve original refresh token if not returned."""
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "ya29.new_access",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid",
                },
            )
        )

        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        tokens = await provider.refresh_tokens("original_refresh_token")

        assert tokens.refresh_token == "original_refresh_token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_tokens_updates_if_new_refresh_token_returned(self):
        """refresh_tokens should use new refresh token if returned."""
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "ya29.new_access",
                    "refresh_token": "new_refresh_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid",
                },
            )
        )

        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        tokens = await provider.refresh_tokens("original_refresh_token")

        assert tokens.refresh_token == "new_refresh_token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_tokens_sends_correct_grant_type(self):
        """refresh_tokens should send refresh_token grant type."""
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "ya29.test",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "openid",
                },
            )
        )

        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        await provider.refresh_tokens("refresh_token_123")

        request = respx.calls.last.request
        body = request.content.decode()
        assert "grant_type=refresh_token" in body


class TestGoogleOAuthProviderUserInfo:
    """Tests for Google OAuth user info retrieval."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user_info_makes_get_request(self):
        """get_user_info should make GET request to userinfo URL."""
        respx.get("https://www.googleapis.com/oauth2/v2/userinfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "123456789",
                    "email": "user@gmail.com",
                    "name": "Test User",
                },
            )
        )

        provider = GoogleOAuthProvider(
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
        respx.get("https://www.googleapis.com/oauth2/v2/userinfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "123456789",
                    "email": "user@gmail.com",
                    "name": "Test User",
                },
            )
        )

        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        user = await provider.get_user_info("access_token_123")

        assert isinstance(user, OAuthUserInfo)
        assert user.external_id == "123456789"
        assert user.email == "user@gmail.com"
        assert user.name == "Test User"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user_info_sends_authorization_header(self):
        """get_user_info should send Bearer token in Authorization header."""
        respx.get("https://www.googleapis.com/oauth2/v2/userinfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "123456789",
                    "email": "user@gmail.com",
                    "name": "Test User",
                },
            )
        )

        provider = GoogleOAuthProvider(
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
        respx.get("https://www.googleapis.com/oauth2/v2/userinfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "123456789",
                },
            )
        )

        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        user = await provider.get_user_info("access_token_123")

        assert user.external_id == "123456789"
        assert user.email is None
        assert user.name is None


class TestGoogleOAuthProviderRevokeToken:
    """Tests for Google OAuth token revocation."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_revoke_token_makes_post_request(self):
        """revoke_token should make POST request to revoke URL."""
        respx.post("https://oauth2.googleapis.com/revoke").mock(
            return_value=httpx.Response(200)
        )

        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        await provider.revoke_token("token_to_revoke")

        assert respx.calls.last.request.method == "POST"

    @pytest.mark.asyncio
    @respx.mock
    async def test_revoke_token_returns_true_on_success(self):
        """revoke_token should return True on successful revocation."""
        respx.post("https://oauth2.googleapis.com/revoke").mock(
            return_value=httpx.Response(200)
        )

        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        result = await provider.revoke_token("token_to_revoke")

        assert result is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_revoke_token_returns_false_on_failure(self):
        """revoke_token should return False on failed revocation."""
        respx.post("https://oauth2.googleapis.com/revoke").mock(
            return_value=httpx.Response(400)
        )

        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        result = await provider.revoke_token("invalid_token")

        assert result is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_revoke_token_sends_token_in_params(self):
        """revoke_token should send token as query parameter."""
        respx.post("https://oauth2.googleapis.com/revoke").mock(
            return_value=httpx.Response(200)
        )

        provider = GoogleOAuthProvider(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://app.example.com/callback",
        )
        await provider.revoke_token("my_token_to_revoke")

        request = respx.calls.last.request
        parsed = urlparse(str(request.url))
        params = parse_qs(parsed.query)
        assert params["token"] == ["my_token_to_revoke"]
