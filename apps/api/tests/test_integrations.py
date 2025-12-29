"""
Integration endpoint tests following TDD (Red-Green-Refactor).

Tests cover:
- POST /integrations/{provider}/connect - Start OAuth flow
- POST /integrations/{provider}/callback - Handle OAuth callback
- DELETE /integrations/{provider}/disconnect - Revoke tokens
- GET /integrations - List connected integrations
- GET /integrations/{provider}/status - Get connection status
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

# =============================================================================
# Fixtures for Integration Testing
# =============================================================================


@pytest.fixture
def test_integration_account_id() -> uuid.UUID:
    """Generate a test integration account ID."""
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def test_state_token() -> str:
    """Generate a test state token for CSRF protection."""
    return "secure-state-token-12345"


@pytest.fixture
def mock_oauth_tokens() -> dict:
    """Mock OAuth token response data."""
    return {
        "access_token": "mock_access_token_12345",
        "refresh_token": "mock_refresh_token_67890",
        "token_type": "Bearer",
        "expires_at": datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        "scopes": ["email", "openid", "https://www.googleapis.com/auth/webmasters.readonly"],
    }


@pytest.fixture
def mock_oauth_user_info() -> dict:
    """Mock OAuth user info response."""
    return {
        "external_id": "external_user_123",
        "email": "oauth_user@example.com",
        "name": "OAuth Test User",
    }


@pytest.fixture
def mock_integration_account(
    test_integration_account_id: uuid.UUID,
    test_user_id: uuid.UUID,
) -> MagicMock:
    """Create a mock integration account."""
    mock_account = MagicMock()
    mock_account.id = test_integration_account_id
    mock_account.user_id = test_user_id
    mock_account.provider = "google_search_console"
    mock_account.provider_account_id = "external_user_123"
    mock_account.token_expires_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    mock_account.scopes = ["email", "openid"]
    mock_account.last_sync_at = None
    mock_account.sync_status = "pending"
    mock_account.sync_error = None
    mock_account.created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    mock_account.updated_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    return mock_account


# =============================================================================
# Test: POST /integrations/{provider}/connect
# =============================================================================


class TestConnectEndpoint:
    """Tests for the POST /integrations/{provider}/connect endpoint."""

    @pytest.mark.asyncio
    async def test_connect_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that connect without authentication returns 401."""
        response = await client.post("/integrations/google_search_console/connect")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_connect_with_valid_provider_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that connect with valid provider returns 200 OK."""
        # Mock no existing integration
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/integrations/google_search_console/connect",
            headers=auth_headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_connect_returns_authorization_url(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that connect response includes authorization_url."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/integrations/google_search_console/connect",
            headers=auth_headers,
        )
        data = response.json()

        assert "authorization_url" in data
        assert isinstance(data["authorization_url"], str)
        assert "accounts.google.com" in data["authorization_url"]

    @pytest.mark.asyncio
    async def test_connect_returns_state_token(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that connect response includes state token for CSRF protection."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/integrations/google_search_console/connect",
            headers=auth_headers,
        )
        data = response.json()

        assert "state" in data
        assert isinstance(data["state"], str)
        assert len(data["state"]) > 0

    @pytest.mark.asyncio
    async def test_connect_with_invalid_provider_returns_400(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Test that connect with invalid provider returns 400."""
        response = await client.post(
            "/integrations/invalid_provider/connect",
            headers=auth_headers,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_connect_when_already_connected_returns_409(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        mock_integration_account: MagicMock,
    ) -> None:
        """Test that connect when already connected returns 409 conflict."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration_account
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/integrations/google_search_console/connect",
            headers=auth_headers,
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_connect_for_google_analytics_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that connect for google_analytics provider works."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/integrations/google_analytics/connect",
            headers=auth_headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_connect_for_bing_webmaster_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that connect for bing_webmaster_tools provider works."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/integrations/bing_webmaster_tools/connect",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "login.microsoftonline.com" in data["authorization_url"]


# =============================================================================
# Test: POST /integrations/{provider}/callback
# =============================================================================


class TestCallbackEndpoint:
    """Tests for the POST /integrations/{provider}/callback endpoint."""

    @pytest.mark.asyncio
    async def test_callback_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that callback without authentication returns 401."""
        response = await client.post(
            "/integrations/google_search_console/callback",
            json={"code": "auth_code", "state": "state_token"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_callback_with_valid_code_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        mock_oauth_tokens: dict,
        mock_oauth_user_info: dict,
        test_user_id: uuid.UUID,
    ) -> None:
        """Test that callback with valid code returns 200 OK."""
        # Mock no existing integration
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        # Store a valid state first using the new async state manager
        from semrush_api.routers.integrations import (
            get_oauth_state_manager,
            reset_oauth_state_manager,
        )
        reset_oauth_state_manager()  # Ensure fresh state
        state_mgr = get_oauth_state_manager()
        await state_mgr.generate(str(test_user_id), "google_search_console")
        # Get the state token that was generated (stored in memory)
        valid_state = list(state_mgr._memory_store.keys())[0]

        with patch(
            "semrush_api.routers.integrations.get_oauth_provider"
        ) as mock_get_oauth_provider:
            mock_provider = AsyncMock()
            mock_provider.exchange_code = AsyncMock(return_value=MagicMock(
                access_token=mock_oauth_tokens["access_token"],
                refresh_token=mock_oauth_tokens["refresh_token"],
                token_type=mock_oauth_tokens["token_type"],
                expires_at=mock_oauth_tokens["expires_at"],
                scopes=mock_oauth_tokens["scopes"],
            ))
            mock_provider.get_user_info = AsyncMock(return_value=MagicMock(
                external_id=mock_oauth_user_info["external_id"],
                email=mock_oauth_user_info["email"],
                name=mock_oauth_user_info["name"],
            ))
            mock_get_oauth_provider.return_value = mock_provider

            response = await client.post(
                "/integrations/google_search_console/callback",
                headers=auth_headers,
                json={"code": "valid_auth_code", "state": valid_state},
            )

        # Clean up state
        reset_oauth_state_manager()

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_callback_returns_integration_data(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        mock_oauth_tokens: dict,
        mock_oauth_user_info: dict,
        test_integration_account_id: uuid.UUID,
        test_user_id: uuid.UUID,
    ) -> None:
        """Test that callback response includes integration details."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        # Create a mock account that will be "created"
        mock_new_account = MagicMock()
        mock_new_account.id = test_integration_account_id
        mock_new_account.provider = "google_search_console"
        mock_new_account.provider_account_id = mock_oauth_user_info["external_id"]

        async def mock_refresh(obj):
            obj.id = test_integration_account_id
            obj.provider = "google_search_console"
            obj.provider_account_id = mock_oauth_user_info["external_id"]

        mock_db_session.refresh = mock_refresh

        # Store a valid state first using the new async state manager
        from semrush_api.routers.integrations import (
            get_oauth_state_manager,
            reset_oauth_state_manager,
        )
        reset_oauth_state_manager()  # Ensure fresh state
        state_mgr = get_oauth_state_manager()
        await state_mgr.generate(str(test_user_id), "google_search_console")
        # Get the state token that was generated (stored in memory)
        valid_state = list(state_mgr._memory_store.keys())[0]

        with patch(
            "semrush_api.routers.integrations.get_oauth_provider"
        ) as mock_get_oauth_provider:
            mock_provider = AsyncMock()
            mock_provider.exchange_code = AsyncMock(return_value=MagicMock(
                access_token=mock_oauth_tokens["access_token"],
                refresh_token=mock_oauth_tokens["refresh_token"],
                token_type=mock_oauth_tokens["token_type"],
                expires_at=mock_oauth_tokens["expires_at"],
                scopes=mock_oauth_tokens["scopes"],
            ))
            mock_provider.get_user_info = AsyncMock(return_value=MagicMock(
                external_id=mock_oauth_user_info["external_id"],
                email=mock_oauth_user_info["email"],
                name=mock_oauth_user_info["name"],
            ))
            mock_get_oauth_provider.return_value = mock_provider

            response = await client.post(
                "/integrations/google_search_console/callback",
                headers=auth_headers,
                json={"code": "valid_auth_code", "state": valid_state},
            )

        # Clean up state
        reset_oauth_state_manager()

        data = response.json()
        assert "provider" in data
        assert "connected" in data
        assert data["connected"] is True

    @pytest.mark.asyncio
    async def test_callback_with_invalid_state_returns_400(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Test that callback with invalid state token returns 400."""
        # No need to mock - the state manager uses in-memory storage in tests
        # and an unknown state will simply not be found
        from semrush_api.routers.integrations import reset_oauth_state_manager
        reset_oauth_state_manager()  # Ensure clean state

        response = await client.post(
            "/integrations/google_search_console/callback",
            headers=auth_headers,
            json={"code": "valid_auth_code", "state": "invalid_state_token"},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_with_missing_code_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Test that callback without code returns 422 validation error."""
        response = await client.post(
            "/integrations/google_search_console/callback",
            headers=auth_headers,
            json={"state": "valid_state_token"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_callback_with_missing_state_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Test that callback without state returns 422 validation error."""
        response = await client.post(
            "/integrations/google_search_console/callback",
            headers=auth_headers,
            json={"code": "valid_auth_code"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_callback_with_invalid_provider_returns_400(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Test that callback with invalid provider returns 400."""
        response = await client.post(
            "/integrations/invalid_provider/callback",
            headers=auth_headers,
            json={"code": "valid_auth_code", "state": "valid_state_token"},
        )
        assert response.status_code == 400


# =============================================================================
# Test: DELETE /integrations/{provider}/disconnect
# =============================================================================


class TestDisconnectEndpoint:
    """Tests for the DELETE /integrations/{provider}/disconnect endpoint."""

    @pytest.mark.asyncio
    async def test_disconnect_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that disconnect without authentication returns 401."""
        response = await client.delete("/integrations/google_search_console/disconnect")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_disconnect_existing_integration_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        mock_integration_account: MagicMock,
    ) -> None:
        """Test that disconnect existing integration returns 200 OK."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration_account
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()
        mock_db_session.commit = AsyncMock()

        with patch(
            "semrush_api.routers.integrations.GoogleOAuthProvider"
        ) as MockGoogleProvider:
            mock_provider = AsyncMock()
            mock_provider.revoke_token = AsyncMock(return_value=True)
            MockGoogleProvider.return_value = mock_provider

            response = await client.delete(
                "/integrations/google_search_console/disconnect",
                headers=auth_headers,
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_disconnect_returns_success_message(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        mock_integration_account: MagicMock,
    ) -> None:
        """Test that disconnect response includes success message."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration_account
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()
        mock_db_session.commit = AsyncMock()

        with patch(
            "semrush_api.routers.integrations.GoogleOAuthProvider"
        ) as MockGoogleProvider:
            mock_provider = AsyncMock()
            mock_provider.revoke_token = AsyncMock(return_value=True)
            MockGoogleProvider.return_value = mock_provider

            response = await client.delete(
                "/integrations/google_search_console/disconnect",
                headers=auth_headers,
            )

        data = response.json()
        assert "message" in data
        assert "disconnected" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_integration_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that disconnect nonexistent integration returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.delete(
            "/integrations/google_search_console/disconnect",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_disconnect_with_invalid_provider_returns_400(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Test that disconnect with invalid provider returns 400."""
        response = await client.delete(
            "/integrations/invalid_provider/disconnect",
            headers=auth_headers,
        )
        assert response.status_code == 400


# =============================================================================
# Test: GET /integrations
# =============================================================================


class TestListIntegrationsEndpoint:
    """Tests for the GET /integrations endpoint."""

    @pytest.mark.asyncio
    async def test_list_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that list without authentication returns 401."""
        response = await client.get("/integrations")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_with_no_integrations_returns_empty_list(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that list with no integrations returns empty list."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/integrations", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "integrations" in data
        assert data["integrations"] == []

    @pytest.mark.asyncio
    async def test_list_with_integrations_returns_all(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        mock_integration_account: MagicMock,
    ) -> None:
        """Test that list returns all connected integrations."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_integration_account]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/integrations", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "integrations" in data
        assert len(data["integrations"]) == 1
        assert data["integrations"][0]["provider"] == "google_search_console"

    @pytest.mark.asyncio
    async def test_list_returns_integration_details(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        mock_integration_account: MagicMock,
    ) -> None:
        """Test that list includes integration details."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_integration_account]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/integrations", headers=auth_headers)

        data = response.json()
        integration = data["integrations"][0]

        assert "provider" in integration
        assert "connected" in integration
        assert "connected_at" in integration


# =============================================================================
# Test: GET /integrations/{provider}/status
# =============================================================================


class TestStatusEndpoint:
    """Tests for the GET /integrations/{provider}/status endpoint."""

    @pytest.mark.asyncio
    async def test_status_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that status without authentication returns 401."""
        response = await client.get("/integrations/google_search_console/status")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_status_for_connected_integration_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        mock_integration_account: MagicMock,
    ) -> None:
        """Test that status for connected integration returns 200."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration_account
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/integrations/google_search_console/status",
            headers=auth_headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_status_returns_connected_true_when_connected(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        mock_integration_account: MagicMock,
    ) -> None:
        """Test that status returns connected=true when integration exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration_account
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/integrations/google_search_console/status",
            headers=auth_headers,
        )
        data = response.json()

        assert data["connected"] is True

    @pytest.mark.asyncio
    async def test_status_returns_connected_false_when_not_connected(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that status returns connected=false when no integration."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/integrations/google_search_console/status",
            headers=auth_headers,
        )
        data = response.json()

        assert response.status_code == 200
        assert data["connected"] is False

    @pytest.mark.asyncio
    async def test_status_includes_provider_info(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        mock_integration_account: MagicMock,
    ) -> None:
        """Test that status includes provider information."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration_account
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/integrations/google_search_console/status",
            headers=auth_headers,
        )
        data = response.json()

        assert "provider" in data
        assert data["provider"] == "google_search_console"

    @pytest.mark.asyncio
    async def test_status_includes_last_sync_info(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        mock_integration_account: MagicMock,
    ) -> None:
        """Test that status includes last sync information."""
        mock_integration_account.last_sync_at = datetime(
            2024, 6, 15, 10, 0, 0, tzinfo=UTC
        )
        mock_integration_account.sync_status = "success"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration_account
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/integrations/google_search_console/status",
            headers=auth_headers,
        )
        data = response.json()

        assert "last_sync_at" in data
        assert "sync_status" in data

    @pytest.mark.asyncio
    async def test_status_with_invalid_provider_returns_400(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Test that status with invalid provider returns 400."""
        response = await client.get(
            "/integrations/invalid_provider/status",
            headers=auth_headers,
        )
        assert response.status_code == 400


# =============================================================================
# Test: Provider Validation
# =============================================================================


class TestProviderValidation:
    """Tests for provider name validation across endpoints."""

    VALID_PROVIDERS = [
        "google_search_console",
        "google_analytics",
        "bing_webmaster_tools",
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider", VALID_PROVIDERS)
    async def test_valid_providers_accepted_for_connect(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        provider: str,
    ) -> None:
        """Test that all valid providers are accepted for connect."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            f"/integrations/{provider}/connect",
            headers=auth_headers,
        )
        # Should not return 400 (invalid provider)
        assert response.status_code != 400

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider", VALID_PROVIDERS)
    async def test_valid_providers_accepted_for_status(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        provider: str,
    ) -> None:
        """Test that all valid providers are accepted for status check."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            f"/integrations/{provider}/status",
            headers=auth_headers,
        )
        # Should not return 400 (invalid provider)
        assert response.status_code != 400

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "invalid_provider",
        ["facebook", "twitter", "linkedin", "invalid", "google-search-console"],
    )
    async def test_invalid_providers_rejected(
        self,
        client: AsyncClient,
        auth_headers: dict,
        invalid_provider: str,
    ) -> None:
        """Test that invalid providers are rejected with 400."""
        response = await client.post(
            f"/integrations/{invalid_provider}/connect",
            headers=auth_headers,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_empty_provider_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Test that empty provider path returns 404 (no matching route)."""
        # Empty provider segment results in a different path that doesn't match
        response = await client.post(
            "/integrations//connect",
            headers=auth_headers,
        )
        # Empty path segment results in 404 as it doesn't match the route
        assert response.status_code == 404


# =============================================================================
# Test: CSRF State Validation
# =============================================================================


class TestCsrfStateValidation:
    """Tests for CSRF state token validation."""

    @pytest.mark.asyncio
    async def test_state_is_unique_per_request(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that each connect request generates a unique state token."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response1 = await client.post(
            "/integrations/google_search_console/connect",
            headers=auth_headers,
        )
        response2 = await client.post(
            "/integrations/google_search_console/connect",
            headers=auth_headers,
        )

        data1 = response1.json()
        data2 = response2.json()

        assert data1["state"] != data2["state"]

    @pytest.mark.asyncio
    async def test_callback_rejects_missing_state(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Test that callback rejects requests without state parameter."""
        response = await client.post(
            "/integrations/google_search_console/callback",
            headers=auth_headers,
            json={"code": "valid_auth_code"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_callback_rejects_invalid_state(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Test that callback rejects requests with invalid state token."""
        # No need to mock - the state manager uses in-memory storage in tests
        # and an unknown state will simply not be found
        from semrush_api.routers.integrations import reset_oauth_state_manager
        reset_oauth_state_manager()  # Ensure clean state

        response = await client.post(
            "/integrations/google_search_console/callback",
            headers=auth_headers,
            json={"code": "valid_auth_code", "state": "unknown_state"},
        )

        assert response.status_code == 400
