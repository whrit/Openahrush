"""
Tests for Token service.

Following TDD: These tests are written FIRST, then the implementation.
Uses mocking for database operations to avoid PostgreSQL-specific types.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from semrush_integrations.oauth.base import OAuthTokens
from semrush_integrations.services.token_service import TokenService


# Create mock classes to simulate database models
class MockIntegrationToken:
    """Mock IntegrationToken for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.integration_account_id = kwargs.get("integration_account_id")
        self.access_token_encrypted = kwargs.get("access_token_encrypted")
        self.refresh_token_encrypted = kwargs.get("refresh_token_encrypted")
        self.token_type = kwargs.get("token_type", "Bearer")
        self.expires_at = kwargs.get("expires_at")
        self.scopes = kwargs.get("scopes", [])


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    return session


@pytest.fixture
def sample_tokens():
    """Create sample OAuth tokens."""
    return OAuthTokens(
        access_token="ya29.test_access_token_value",
        refresh_token="1//test_refresh_token_value",
        token_type="Bearer",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes=["openid", "email"],
    )


@pytest.fixture
def sample_account_id():
    """Create a sample account ID."""
    return uuid.uuid4()


class TestTokenServiceStoreTokens:
    """Tests for storing OAuth tokens."""

    @patch("semrush_integrations.services.token_service.encrypt_token")
    def test_store_tokens_encrypts_access_token(self, mock_encrypt, mock_db_session, sample_account_id, sample_tokens):
        """Should encrypt the access token before storing."""
        mock_encrypt.return_value = "encrypted_access"

        service = TokenService(mock_db_session)
        service.store_tokens(sample_account_id, sample_tokens)

        # Verify encrypt_token was called with the access token
        assert any(call[0][0] == sample_tokens.access_token for call in mock_encrypt.call_args_list)

    @patch("semrush_integrations.services.token_service.encrypt_token")
    def test_store_tokens_encrypts_refresh_token(self, mock_encrypt, mock_db_session, sample_account_id, sample_tokens):
        """Should encrypt the refresh token before storing."""
        mock_encrypt.return_value = "encrypted_refresh"

        service = TokenService(mock_db_session)
        service.store_tokens(sample_account_id, sample_tokens)

        # Verify encrypt_token was called with the refresh token
        assert any(call[0][0] == sample_tokens.refresh_token for call in mock_encrypt.call_args_list)

    @patch("semrush_integrations.services.token_service.encrypt_token")
    def test_store_tokens_handles_none_refresh_token(self, mock_encrypt, mock_db_session, sample_account_id):
        """Should handle None refresh token."""
        tokens = OAuthTokens(
            access_token="ya29.test_access",
            refresh_token=None,
            token_type="Bearer",
            expires_at=None,
            scopes=[],
        )
        mock_encrypt.return_value = "encrypted"

        service = TokenService(mock_db_session)
        service.store_tokens(sample_account_id, tokens)

        # Should only encrypt the access token, not refresh token
        assert mock_encrypt.call_count == 1
        mock_encrypt.assert_called_once_with(tokens.access_token)

    @patch("semrush_integrations.services.token_service.encrypt_token")
    @patch("semrush_integrations.services.token_service.IntegrationToken")
    def test_store_tokens_creates_new_record(self, MockToken, mock_encrypt, mock_db_session, sample_account_id, sample_tokens):
        """Should create a new IntegrationToken when none exists."""
        mock_encrypt.return_value = "encrypted"
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        service = TokenService(mock_db_session)
        service.store_tokens(sample_account_id, sample_tokens)

        # Should have added a new token to the session
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @patch("semrush_integrations.services.token_service.encrypt_token")
    def test_store_tokens_updates_existing_record(self, mock_encrypt, mock_db_session, sample_account_id, sample_tokens):
        """Should update existing token instead of creating duplicate."""
        mock_encrypt.return_value = "encrypted"
        existing_token = MockIntegrationToken(integration_account_id=sample_account_id)
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_token

        service = TokenService(mock_db_session)
        service.store_tokens(sample_account_id, sample_tokens)

        # Should NOT add a new token (updating existing)
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_called_once()

    @patch("semrush_integrations.services.token_service.encrypt_token")
    def test_store_tokens_saves_token_type(self, mock_encrypt, mock_db_session, sample_account_id, sample_tokens):
        """Should save the token type."""
        mock_encrypt.return_value = "encrypted"
        existing_token = MockIntegrationToken(integration_account_id=sample_account_id)
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_token

        service = TokenService(mock_db_session)
        service.store_tokens(sample_account_id, sample_tokens)

        assert existing_token.token_type == "Bearer"

    @patch("semrush_integrations.services.token_service.encrypt_token")
    def test_store_tokens_saves_expires_at(self, mock_encrypt, mock_db_session, sample_account_id, sample_tokens):
        """Should save the expiration time."""
        mock_encrypt.return_value = "encrypted"
        existing_token = MockIntegrationToken(integration_account_id=sample_account_id)
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_token

        service = TokenService(mock_db_session)
        service.store_tokens(sample_account_id, sample_tokens)

        assert existing_token.expires_at == sample_tokens.expires_at

    @patch("semrush_integrations.services.token_service.encrypt_token")
    def test_store_tokens_saves_scopes(self, mock_encrypt, mock_db_session, sample_account_id, sample_tokens):
        """Should save the scopes list."""
        mock_encrypt.return_value = "encrypted"
        existing_token = MockIntegrationToken(integration_account_id=sample_account_id)
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_token

        service = TokenService(mock_db_session)
        service.store_tokens(sample_account_id, sample_tokens)

        assert existing_token.scopes == ["openid", "email"]


class TestTokenServiceGetValidToken:
    """Tests for retrieving valid tokens."""

    @patch("semrush_integrations.services.token_service.decrypt_token")
    def test_get_valid_token_decrypts_access_token(self, mock_decrypt, mock_db_session, sample_account_id):
        """Should return decrypted access token."""
        mock_token = MockIntegrationToken(
            integration_account_id=sample_account_id,
            access_token_encrypted=b"encrypted_access",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_token
        mock_decrypt.return_value = "decrypted_access_token"

        service = TokenService(mock_db_session)
        mock_provider = MagicMock()
        result = service.get_valid_token(sample_account_id, mock_provider)

        assert result == "decrypted_access_token"

    def test_get_valid_token_raises_for_missing_token(self, mock_db_session, sample_account_id):
        """Should raise ValueError when no token exists."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        service = TokenService(mock_db_session)
        mock_provider = MagicMock()

        with pytest.raises(ValueError, match="No token found"):
            service.get_valid_token(sample_account_id, mock_provider)

    @patch("semrush_integrations.services.token_service.decrypt_token")
    def test_get_valid_token_refreshes_expired_token(self, mock_decrypt, mock_db_session, sample_account_id):
        """Should refresh token when expired."""
        # Create expired token
        mock_token = MockIntegrationToken(
            integration_account_id=sample_account_id,
            access_token_encrypted=b"encrypted_access",
            refresh_token_encrypted=b"encrypted_refresh",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_token
        mock_decrypt.return_value = "decrypted_refresh_token"

        # Mock provider that returns new tokens
        mock_provider = MagicMock()
        new_tokens = OAuthTokens(
            access_token="ya29.new_access_token",
            refresh_token="1//new_refresh_token",
            token_type="Bearer",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            scopes=["openid"],
        )
        mock_provider.refresh_tokens = AsyncMock(return_value=new_tokens)

        service = TokenService(mock_db_session)

        with patch.object(service, "store_tokens"):
            result = service.get_valid_token(sample_account_id, mock_provider)

        # Should have called refresh_tokens
        mock_provider.refresh_tokens.assert_called_once()
        # Should return new access token
        assert result == "ya29.new_access_token"

    @patch("semrush_integrations.services.token_service.decrypt_token")
    def test_get_valid_token_refreshes_near_expiry_token(self, mock_decrypt, mock_db_session, sample_account_id):
        """Should refresh token when within 5 minutes of expiry."""
        # Create token expiring in 3 minutes
        mock_token = MockIntegrationToken(
            integration_account_id=sample_account_id,
            access_token_encrypted=b"encrypted_access",
            refresh_token_encrypted=b"encrypted_refresh",
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_token
        mock_decrypt.return_value = "decrypted_refresh_token"

        # Mock provider
        mock_provider = MagicMock()
        new_tokens = OAuthTokens(
            access_token="ya29.refreshed_token",
            refresh_token="1//new_refresh",
            token_type="Bearer",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            scopes=["openid"],
        )
        mock_provider.refresh_tokens = AsyncMock(return_value=new_tokens)

        service = TokenService(mock_db_session)

        with patch.object(service, "store_tokens"):
            result = service.get_valid_token(sample_account_id, mock_provider)

        mock_provider.refresh_tokens.assert_called_once()
        assert result == "ya29.refreshed_token"

    def test_get_valid_token_raises_without_refresh_token(self, mock_db_session, sample_account_id):
        """Should raise ValueError when token expired and no refresh token."""
        mock_token = MockIntegrationToken(
            integration_account_id=sample_account_id,
            access_token_encrypted=b"encrypted_access",
            refresh_token_encrypted=None,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_token

        service = TokenService(mock_db_session)
        mock_provider = MagicMock()

        with pytest.raises(ValueError, match="no refresh token"):
            service.get_valid_token(sample_account_id, mock_provider)


class TestTokenServiceRevokeTokens:
    """Tests for revoking tokens."""

    @patch("semrush_integrations.services.token_service.decrypt_token")
    def test_revoke_tokens_calls_provider_revoke(self, mock_decrypt, mock_db_session, sample_account_id):
        """Should call provider's revoke_token method."""
        mock_token = MockIntegrationToken(
            integration_account_id=sample_account_id,
            access_token_encrypted=b"encrypted_access",
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_token
        mock_decrypt.return_value = "decrypted_access"

        mock_provider = MagicMock()
        mock_provider.revoke_token = AsyncMock(return_value=True)

        service = TokenService(mock_db_session)
        service.revoke_tokens(sample_account_id, mock_provider)

        mock_provider.revoke_token.assert_called_once_with("decrypted_access")

    @patch("semrush_integrations.services.token_service.decrypt_token")
    def test_revoke_tokens_deletes_token_record(self, mock_decrypt, mock_db_session, sample_account_id):
        """Should delete the token record from database."""
        mock_token = MockIntegrationToken(
            integration_account_id=sample_account_id,
            access_token_encrypted=b"encrypted_access",
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_token
        mock_decrypt.return_value = "decrypted_access"

        mock_provider = MagicMock()
        mock_provider.revoke_token = AsyncMock(return_value=True)

        service = TokenService(mock_db_session)
        service.revoke_tokens(sample_account_id, mock_provider)

        mock_db_session.delete.assert_called_once_with(mock_token)
        mock_db_session.commit.assert_called_once()

    @patch("semrush_integrations.services.token_service.decrypt_token")
    def test_revoke_tokens_returns_true_on_success(self, mock_decrypt, mock_db_session, sample_account_id):
        """Should return True on successful revocation."""
        mock_token = MockIntegrationToken(
            integration_account_id=sample_account_id,
            access_token_encrypted=b"encrypted_access",
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_token
        mock_decrypt.return_value = "decrypted_access"

        mock_provider = MagicMock()
        mock_provider.revoke_token = AsyncMock(return_value=True)

        service = TokenService(mock_db_session)
        result = service.revoke_tokens(sample_account_id, mock_provider)

        assert result is True

    def test_revoke_tokens_returns_false_for_missing_token(self, mock_db_session, sample_account_id):
        """Should return False when no token exists."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        mock_provider = MagicMock()

        service = TokenService(mock_db_session)
        result = service.revoke_tokens(sample_account_id, mock_provider)

        assert result is False
        mock_provider.revoke_token.assert_not_called()


class TestTokenServiceDecryptToken:
    """Tests for token decryption helper."""

    @patch("semrush_integrations.services.token_service.decrypt_token")
    def test_decrypt_access_token_returns_decrypted_value(self, mock_decrypt, mock_db_session):
        """Decrypted token should match original plaintext."""
        mock_token = MockIntegrationToken(
            access_token_encrypted=b"encrypted_access_token",
        )
        mock_decrypt.return_value = "decrypted_access_token"

        service = TokenService(mock_db_session)
        result = service.decrypt_access_token(mock_token)

        assert result == "decrypted_access_token"

    @patch("semrush_integrations.services.token_service.decrypt_token")
    def test_decrypt_refresh_token_returns_decrypted_value(self, mock_decrypt, mock_db_session):
        """Decrypted refresh token should match original plaintext."""
        mock_token = MockIntegrationToken(
            refresh_token_encrypted=b"encrypted_refresh_token",
        )
        mock_decrypt.return_value = "decrypted_refresh_token"

        service = TokenService(mock_db_session)
        result = service.decrypt_refresh_token(mock_token)

        assert result == "decrypted_refresh_token"

    def test_decrypt_refresh_token_returns_none_for_none(self, mock_db_session):
        """Should return None when refresh token is None."""
        mock_token = MockIntegrationToken(
            refresh_token_encrypted=None,
        )

        service = TokenService(mock_db_session)
        result = service.decrypt_refresh_token(mock_token)

        assert result is None
