"""
Health endpoint tests following TDD (Red-Green-Refactor).

Tests cover:
- Liveness check (/healthz) - basic app availability
- Readiness check (/readyz) - dependency health including database
"""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from sqlalchemy import text


class TestHealthzEndpoint:
    """Tests for the /healthz liveness probe endpoint."""

    @pytest.mark.asyncio
    async def test_healthz_returns_200_ok(self, client: AsyncClient) -> None:
        """
        Test that /healthz returns 200 OK when the API is running.

        This is the most basic liveness check - if the API is up,
        this endpoint should respond successfully.
        """
        response = await client.get("/healthz")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_healthz_returns_ok_status(self, client: AsyncClient) -> None:
        """
        Test that /healthz response contains ok: true.

        The response should clearly indicate the service is healthy.
        """
        response = await client.get("/healthz")
        data = response.json()

        assert data["ok"] is True

    @pytest.mark.asyncio
    async def test_healthz_returns_version(self, client: AsyncClient) -> None:
        """
        Test that /healthz response includes API version.

        Version info helps with debugging and deployment verification.
        """
        response = await client.get("/healthz")
        data = response.json()

        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0


class TestReadyzEndpoint:
    """Tests for the /readyz readiness probe endpoint."""

    @pytest.mark.asyncio
    async def test_readyz_returns_200_when_db_connected(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that /readyz returns 200 OK when database is connected.

        The readiness check should verify all critical dependencies
        and return 200 only when everything is healthy.
        """
        # Configure mock to simulate successful DB query
        mock_result = AsyncMock()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/readyz")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_readyz_returns_ok_status_when_healthy(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that /readyz response contains ok: true when all checks pass.
        """
        mock_result = AsyncMock()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/readyz")
        data = response.json()

        assert data["ok"] is True

    @pytest.mark.asyncio
    async def test_readyz_includes_database_status(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that /readyz includes database connection status.

        The response should provide visibility into individual
        dependency health for debugging.
        """
        mock_result = AsyncMock()
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/readyz")
        data = response.json()

        assert "checks" in data
        assert "database" in data["checks"]
        assert data["checks"]["database"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_readyz_returns_503_when_db_unavailable(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that /readyz returns 503 Service Unavailable when database is down.

        This is critical for proper load balancer behavior - unhealthy
        instances should be removed from rotation.
        """
        # Configure mock to simulate DB connection failure
        mock_db_session.execute = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        response = await client.get("/readyz")

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_readyz_returns_error_status_when_db_unavailable(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that /readyz response contains ok: false when database is down.
        """
        mock_db_session.execute = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        response = await client.get("/readyz")
        data = response.json()

        assert data["ok"] is False

    @pytest.mark.asyncio
    async def test_readyz_includes_error_details_when_db_fails(
        self,
        client: AsyncClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that /readyz includes error message when database check fails.

        Error details help with troubleshooting.
        """
        mock_db_session.execute = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        response = await client.get("/readyz")
        data = response.json()

        assert "checks" in data
        assert "database" in data["checks"]
        assert data["checks"]["database"]["status"] == "error"
        assert "error" in data["checks"]["database"]
