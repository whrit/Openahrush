"""
Tests for OAuth provider base class.

Following TDD: These tests are written FIRST, then the implementation.
"""

import pytest
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from semrush_integrations.oauth.base import OAuthProvider, OAuthTokens, OAuthUserInfo


class ConcreteOAuthProvider(OAuthProvider):
    """Concrete implementation for testing abstract base class."""

    provider_name = "test_provider"
    authorization_url = "https://test.example.com/oauth/authorize"
    token_url = "https://test.example.com/oauth/token"
    scopes = ["scope1", "scope2"]

    async def exchange_code(self, code: str) -> OAuthTokens:
        return OAuthTokens(
            access_token="test_access",
            refresh_token="test_refresh",
            token_type="Bearer",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            scopes=["scope1"],
        )

    async def refresh_tokens(self, refresh_token: str) -> OAuthTokens:
        return OAuthTokens(
            access_token="new_access",
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            scopes=["scope1"],
        )

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        return OAuthUserInfo(
            external_id="ext123",
            email="test@example.com",
            name="Test User",
        )

    async def revoke_token(self, token: str) -> bool:
        return True


class TestOAuthTokensDataclass:
    """Tests for OAuthTokens dataclass."""

    def test_oauth_tokens_creation(self):
        """Should create OAuthTokens with all fields."""
        expires = datetime.utcnow() + timedelta(hours=1)
        tokens = OAuthTokens(
            access_token="access123",
            refresh_token="refresh456",
            token_type="Bearer",
            expires_at=expires,
            scopes=["email", "profile"],
        )
        assert tokens.access_token == "access123"
        assert tokens.refresh_token == "refresh456"
        assert tokens.token_type == "Bearer"
        assert tokens.expires_at == expires
        assert tokens.scopes == ["email", "profile"]

    def test_oauth_tokens_optional_refresh_token(self):
        """Refresh token should be optional."""
        tokens = OAuthTokens(
            access_token="access123",
            refresh_token=None,
            token_type="Bearer",
            expires_at=None,
            scopes=[],
        )
        assert tokens.refresh_token is None

    def test_oauth_tokens_optional_expires_at(self):
        """Expires at should be optional."""
        tokens = OAuthTokens(
            access_token="access123",
            refresh_token="refresh456",
            token_type="Bearer",
            expires_at=None,
            scopes=[],
        )
        assert tokens.expires_at is None


class TestOAuthUserInfoDataclass:
    """Tests for OAuthUserInfo dataclass."""

    def test_oauth_user_info_creation(self):
        """Should create OAuthUserInfo with all fields."""
        user = OAuthUserInfo(
            external_id="ext123",
            email="user@example.com",
            name="John Doe",
        )
        assert user.external_id == "ext123"
        assert user.email == "user@example.com"
        assert user.name == "John Doe"

    def test_oauth_user_info_optional_fields(self):
        """Email and name should be optional."""
        user = OAuthUserInfo(
            external_id="ext123",
            email=None,
            name=None,
        )
        assert user.external_id == "ext123"
        assert user.email is None
        assert user.name is None


class TestOAuthProviderInitialization:
    """Tests for OAuth provider initialization."""

    def test_provider_initialization(self):
        """Should initialize with client credentials."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        assert provider.client_id == "client123"
        assert provider.client_secret == "secret456"
        assert provider.redirect_uri == "https://app.example.com/callback"

    def test_provider_has_required_attributes(self):
        """Provider should have required class attributes."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        assert provider.provider_name == "test_provider"
        assert provider.authorization_url == "https://test.example.com/oauth/authorize"
        assert provider.token_url == "https://test.example.com/oauth/token"
        assert provider.scopes == ["scope1", "scope2"]


class TestOAuthProviderAuthorizationUrl:
    """Tests for OAuth authorization URL generation."""

    def test_get_authorization_url_contains_client_id(self):
        """Authorization URL should contain client ID."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        url = provider.get_authorization_url("state_token")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["client_id"] == ["client123"]

    def test_get_authorization_url_contains_redirect_uri(self):
        """Authorization URL should contain redirect URI."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        url = provider.get_authorization_url("state_token")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["redirect_uri"] == ["https://app.example.com/callback"]

    def test_get_authorization_url_contains_state(self):
        """Authorization URL should contain state parameter."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        url = provider.get_authorization_url("my_state_token")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["state"] == ["my_state_token"]

    def test_get_authorization_url_contains_scopes(self):
        """Authorization URL should contain scopes."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        url = provider.get_authorization_url("state_token")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["scope"] == ["scope1 scope2"]

    def test_get_authorization_url_uses_base_url(self):
        """Authorization URL should use the provider's authorization URL."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        url = provider.get_authorization_url("state_token")
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "test.example.com"
        assert parsed.path == "/oauth/authorize"

    def test_get_authorization_url_includes_response_type_code(self):
        """Authorization URL should request authorization code."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        url = provider.get_authorization_url("state_token")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["response_type"] == ["code"]

    def test_get_authorization_url_includes_offline_access(self):
        """Authorization URL should request offline access for refresh tokens."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        url = provider.get_authorization_url("state_token")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["access_type"] == ["offline"]

    def test_get_authorization_url_prompts_consent(self):
        """Authorization URL should prompt for consent."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        url = provider.get_authorization_url("state_token")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["prompt"] == ["consent"]


class TestOAuthProviderAbstractMethods:
    """Tests verifying abstract methods must be implemented."""

    @pytest.mark.asyncio
    async def test_exchange_code_returns_tokens(self):
        """exchange_code should return OAuthTokens."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        tokens = await provider.exchange_code("auth_code")
        assert isinstance(tokens, OAuthTokens)
        assert tokens.access_token == "test_access"

    @pytest.mark.asyncio
    async def test_refresh_tokens_returns_new_tokens(self):
        """refresh_tokens should return new OAuthTokens."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        tokens = await provider.refresh_tokens("old_refresh")
        assert isinstance(tokens, OAuthTokens)
        assert tokens.access_token == "new_access"

    @pytest.mark.asyncio
    async def test_get_user_info_returns_user_info(self):
        """get_user_info should return OAuthUserInfo."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        user = await provider.get_user_info("access_token")
        assert isinstance(user, OAuthUserInfo)
        assert user.external_id == "ext123"

    @pytest.mark.asyncio
    async def test_revoke_token_returns_bool(self):
        """revoke_token should return boolean."""
        provider = ConcreteOAuthProvider(
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
        )
        result = await provider.revoke_token("token")
        assert isinstance(result, bool)
        assert result is True
