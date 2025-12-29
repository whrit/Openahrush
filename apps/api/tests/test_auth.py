"""
Authentication endpoint tests following TDD (Red-Green-Refactor).

Tests cover:
- POST /auth/register - user registration
- POST /auth/login - credential validation and JWT issuance
- POST /auth/logout - session acknowledgement
- GET /me - current user information retrieval
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


class TestRegisterEndpoint:
    """Tests for the POST /auth/register endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that registration with valid data returns 201 Created.

        A new user should be created and user info returned.
        """
        # Mock that no existing user is found (email is unique)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Mock the new user that gets created
        new_user_id = uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")
        mock_new_user = MagicMock()
        mock_new_user.id = new_user_id
        mock_new_user.email = "newuser@example.com"
        mock_new_user.name = "New User"
        mock_new_user.is_active = True

        # Configure the mock for refresh to set up the user
        async def mock_refresh(user):
            user.id = new_user_id
            user.email = "newuser@example.com"
            user.name = "New User"
            user.is_active = True

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        response = await client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "name": "New User",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["name"] == "New User"
        assert data["is_active"] is True
        assert "id" in data
        assert "password" not in data
        assert "password_hash" not in data

    @pytest.mark.asyncio
    async def test_register_success_without_name(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that registration without a name succeeds.

        Name is optional in the registration request.
        """
        # Mock that no existing user is found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        new_user_id = uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")

        async def mock_refresh(user):
            user.id = new_user_id
            user.email = "newuser@example.com"
            user.name = None
            user.is_active = True

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        response = await client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["name"] is None

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
        test_user_data: dict,
    ) -> None:
        """
        Test that registration with existing email returns 409 Conflict.

        Duplicate emails should not be allowed.
        """
        # Mock that an existing user IS found
        mock_user = MagicMock()
        mock_user.id = test_user_data["id"]
        mock_user.email = test_user_data["email"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/auth/register",
            json={
                "email": test_user_data["email"],
                "password": "securepassword123",
                "name": "Duplicate User",
            },
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_weak_password(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that registration with password less than 8 chars returns 422.

        Passwords must be at least 8 characters.
        """
        response = await client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "short",  # Only 5 characters
                "name": "New User",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that registration with invalid email format returns 422.

        Email must be a valid email address.
        """
        response = await client.post(
            "/auth/register",
            json={
                "email": "not-an-email",
                "password": "securepassword123",
                "name": "New User",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_missing_email(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that registration without email returns 422.

        Email is a required field.
        """
        response = await client.post(
            "/auth/register",
            json={
                "password": "securepassword123",
                "name": "New User",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_missing_password(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that registration without password returns 422.

        Password is a required field.
        """
        response = await client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "name": "New User",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_does_not_expose_password_hash(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that registration response does not include password hash.

        Password hashes should never be exposed in API responses.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        new_user_id = uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")

        async def mock_refresh(user):
            user.id = new_user_id
            user.email = "newuser@example.com"
            user.name = "New User"
            user.is_active = True

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        response = await client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "name": "New User",
            },
        )

        data = response.json()
        assert "password_hash" not in data
        assert "password" not in data


class TestLoginEndpoint:
    """Tests for the POST /auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_with_valid_credentials_returns_200(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
        test_user_email: str,
        test_user_password: str,
        test_user_data: dict,
    ) -> None:
        """
        Test that login with valid credentials returns 200 OK.

        A user with correct email/password should receive a successful response.
        """
        # Mock the user lookup
        mock_user = MagicMock()
        mock_user.id = test_user_data["id"]
        mock_user.email = test_user_data["email"]
        mock_user.password_hash = test_user_data["password_hash"]
        mock_user.name = test_user_data["name"]
        mock_user.is_active = test_user_data["is_active"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/auth/login",
            json={
                "email": test_user_email,
                "password": test_user_password,
            },
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_login_with_valid_credentials_returns_access_token(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
        test_user_email: str,
        test_user_password: str,
        test_user_data: dict,
    ) -> None:
        """
        Test that login response includes access_token.

        The token should be returned for client-side storage.
        """
        mock_user = MagicMock()
        mock_user.id = test_user_data["id"]
        mock_user.email = test_user_data["email"]
        mock_user.password_hash = test_user_data["password_hash"]
        mock_user.name = test_user_data["name"]
        mock_user.is_active = test_user_data["is_active"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/auth/login",
            json={
                "email": test_user_email,
                "password": test_user_password,
            },
        )
        data = response.json()

        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

    @pytest.mark.asyncio
    async def test_login_with_valid_credentials_returns_token_type(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
        test_user_email: str,
        test_user_password: str,
        test_user_data: dict,
    ) -> None:
        """
        Test that login response includes token_type: bearer.

        This follows OAuth 2.0 token response format.
        """
        mock_user = MagicMock()
        mock_user.id = test_user_data["id"]
        mock_user.email = test_user_data["email"]
        mock_user.password_hash = test_user_data["password_hash"]
        mock_user.name = test_user_data["name"]
        mock_user.is_active = test_user_data["is_active"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/auth/login",
            json={
                "email": test_user_email,
                "password": test_user_password,
            },
        )
        data = response.json()

        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_with_valid_credentials_returns_expires_in(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
        test_user_email: str,
        test_user_password: str,
        test_user_data: dict,
    ) -> None:
        """
        Test that login response includes expires_in.

        Clients need to know when to refresh the token.
        """
        mock_user = MagicMock()
        mock_user.id = test_user_data["id"]
        mock_user.email = test_user_data["email"]
        mock_user.password_hash = test_user_data["password_hash"]
        mock_user.name = test_user_data["name"]
        mock_user.is_active = test_user_data["is_active"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/auth/login",
            json={
                "email": test_user_email,
                "password": test_user_password,
            },
        )
        data = response.json()

        assert "expires_in" in data
        assert isinstance(data["expires_in"], int)
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_login_with_invalid_email_returns_401(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that login with non-existent email returns 401.

        Unknown users should not be able to authenticate.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "anypassword",
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_with_invalid_password_returns_401(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
        test_user_email: str,
        test_user_data: dict,
    ) -> None:
        """
        Test that login with wrong password returns 401.

        Incorrect passwords should fail authentication.
        """
        mock_user = MagicMock()
        mock_user.id = test_user_data["id"]
        mock_user.email = test_user_data["email"]
        mock_user.password_hash = test_user_data["password_hash"]
        mock_user.name = test_user_data["name"]
        mock_user.is_active = test_user_data["is_active"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/auth/login",
            json={
                "email": test_user_email,
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_with_inactive_user_returns_401(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
        test_user_email: str,
        test_user_password: str,
        test_user_data: dict,
    ) -> None:
        """
        Test that login with deactivated account returns 401.

        Inactive users should not be able to authenticate.
        """
        mock_user = MagicMock()
        mock_user.id = test_user_data["id"]
        mock_user.email = test_user_data["email"]
        mock_user.password_hash = test_user_data["password_hash"]
        mock_user.name = test_user_data["name"]
        mock_user.is_active = False  # Deactivated

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            "/auth/login",
            json={
                "email": test_user_email,
                "password": test_user_password,
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_with_missing_email_returns_422(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that login without email returns 422 validation error.
        """
        response = await client.post(
            "/auth/login",
            json={
                "password": "somepassword",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_with_missing_password_returns_422(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that login without password returns 422 validation error.
        """
        response = await client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
            },
        )

        assert response.status_code == 422


class TestLogoutEndpoint:
    """Tests for the POST /auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_with_valid_token_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """
        Test that logout with valid token returns 200 OK.
        """
        response = await client.post("/auth/logout", headers=auth_headers)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_logout_returns_success_message(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """
        Test that logout response includes success message.
        """
        response = await client.post("/auth/logout", headers=auth_headers)
        data = response.json()

        assert "message" in data
        assert data["message"] == "Successfully logged out"

    @pytest.mark.asyncio
    async def test_logout_without_token_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that logout without authentication returns 401.
        """
        response = await client.post("/auth/logout")

        assert response.status_code == 401


class TestMeEndpoint:
    """Tests for the GET /me endpoint."""

    @pytest.mark.asyncio
    async def test_me_without_token_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that /me without authentication returns 401.

        This endpoint requires authentication.
        """
        response = await client.get("/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_valid_token_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_user_data: dict,
    ) -> None:
        """
        Test that /me with valid token returns 200 OK.
        """
        mock_user = MagicMock()
        mock_user.id = test_user_data["id"]
        mock_user.email = test_user_data["email"]
        mock_user.name = test_user_data["name"]
        mock_user.is_active = test_user_data["is_active"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/me", headers=auth_headers)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_me_with_valid_token_returns_user_id(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_user_data: dict,
    ) -> None:
        """
        Test that /me response includes user ID.
        """
        mock_user = MagicMock()
        mock_user.id = test_user_data["id"]
        mock_user.email = test_user_data["email"]
        mock_user.name = test_user_data["name"]
        mock_user.is_active = test_user_data["is_active"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/me", headers=auth_headers)
        data = response.json()

        assert "id" in data
        assert data["id"] == str(test_user_data["id"])

    @pytest.mark.asyncio
    async def test_me_with_valid_token_returns_email(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_user_data: dict,
    ) -> None:
        """
        Test that /me response includes user email.
        """
        mock_user = MagicMock()
        mock_user.id = test_user_data["id"]
        mock_user.email = test_user_data["email"]
        mock_user.name = test_user_data["name"]
        mock_user.is_active = test_user_data["is_active"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/me", headers=auth_headers)
        data = response.json()

        assert "email" in data
        assert data["email"] == test_user_data["email"]

    @pytest.mark.asyncio
    async def test_me_with_valid_token_returns_name(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_user_data: dict,
    ) -> None:
        """
        Test that /me response includes user name.
        """
        mock_user = MagicMock()
        mock_user.id = test_user_data["id"]
        mock_user.email = test_user_data["email"]
        mock_user.name = test_user_data["name"]
        mock_user.is_active = test_user_data["is_active"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/me", headers=auth_headers)
        data = response.json()

        assert "name" in data
        assert data["name"] == test_user_data["name"]

    @pytest.mark.asyncio
    async def test_me_does_not_expose_password_hash(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_user_data: dict,
    ) -> None:
        """
        Test that /me response does not include password hash.

        Password hashes should never be exposed in API responses.
        """
        mock_user = MagicMock()
        mock_user.id = test_user_data["id"]
        mock_user.email = test_user_data["email"]
        mock_user.name = test_user_data["name"]
        mock_user.is_active = test_user_data["is_active"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/me", headers=auth_headers)
        data = response.json()

        assert "password_hash" not in data
        assert "password" not in data

    @pytest.mark.asyncio
    async def test_me_with_invalid_token_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that /me with invalid token returns 401.
        """
        response = await client.get(
            "/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_expired_token_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Test that /me with expired token returns 401.
        """
        # Create an expired token (this is a mock, the actual expiry
        # would be handled by JWT decode)
        from datetime import timedelta

        from semrush_core.security.jwt import create_access_token

        expired_token = create_access_token(
            "12345678-1234-5678-1234-567812345678",
            expires_delta=timedelta(seconds=-1),  # Already expired
        )

        response = await client.get(
            "/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401
