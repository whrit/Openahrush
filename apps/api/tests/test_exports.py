"""
Tests for Export endpoints following TDD (Red-Green-Refactor).

Tests cover:
- POST /projects/{project_id}/exports - Create export job
- GET /projects/{project_id}/exports - List exports with pagination
- GET /projects/{project_id}/exports/{export_id} - Get export status
- GET /projects/{project_id}/exports/{export_id}/download - Get download URL
- Authorization (user can only access own project's exports)
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


class TestCreateExport:
    """Tests for the POST /projects/{project_id}/exports endpoint."""

    @pytest.mark.asyncio
    async def test_create_export_returns_202_accepted(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """
        Test that creating an export returns 202 Accepted.

        Export creation should be asynchronous, so it returns 202.
        """
        # Setup: Project exists and is owned by user
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        # Mock the created export
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)

        async def mock_refresh(obj):
            obj.id = export_id
            obj.project_id = test_project_id
            obj.format = "csv"
            obj.resource = "issues"
            obj.status = "queued"
            obj.params = {}
            obj.artifact_key = None
            obj.file_size_bytes = None
            obj.download_url = None
            obj.download_expires_at = None
            obj.error_message = None
            obj.started_at = None
            obj.completed_at = None
            obj.created_at = created_at

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={
                "format": "csv",
                "resource": "issues",
            },
        )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_create_export_returns_export_record(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """
        Test that creating an export returns the export record.

        The response should include id, format, resource, status, etc.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)

        async def mock_refresh(obj):
            obj.id = export_id
            obj.project_id = test_project_id
            obj.format = "json"
            obj.resource = "backlinks"
            obj.status = "queued"
            obj.params = {"source_type": "commoncrawl"}
            obj.artifact_key = None
            obj.file_size_bytes = None
            obj.download_url = None
            obj.download_expires_at = None
            obj.error_message = None
            obj.started_at = None
            obj.completed_at = None
            obj.created_at = created_at

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={
                "format": "json",
                "resource": "backlinks",
                "params": {"source_type": "commoncrawl"},
            },
        )

        data = response.json()
        assert data["id"] == str(export_id)
        assert data["project_id"] == str(test_project_id)
        assert data["format"] == "json"
        assert data["resource"] == "backlinks"
        assert data["status"] == "queued"
        assert data["params"] == {"source_type": "commoncrawl"}
        assert data["download_url"] is None
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_export_with_csv_format(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that CSV format is accepted."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
            obj.project_id = test_project_id
            obj.format = "csv"
            obj.resource = "issues"
            obj.status = "queued"
            obj.params = {}
            obj.artifact_key = None
            obj.file_size_bytes = None
            obj.download_url = None
            obj.download_expires_at = None
            obj.error_message = None
            obj.started_at = None
            obj.completed_at = None
            obj.created_at = datetime.now(UTC)

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={"format": "csv", "resource": "issues"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["format"] == "csv"

    @pytest.mark.asyncio
    async def test_create_export_with_json_format(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that JSON format is accepted."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
            obj.project_id = test_project_id
            obj.format = "json"
            obj.resource = "issues"
            obj.status = "queued"
            obj.params = {}
            obj.artifact_key = None
            obj.file_size_bytes = None
            obj.download_url = None
            obj.download_expires_at = None
            obj.error_message = None
            obj.started_at = None
            obj.completed_at = None
            obj.created_at = datetime.now(UTC)

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={"format": "json", "resource": "issues"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["format"] == "json"

    @pytest.mark.asyncio
    async def test_create_export_with_invalid_format_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that invalid format returns validation error."""
        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={"format": "invalid_format", "resource": "issues"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_export_with_invalid_resource_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that invalid resource returns validation error."""
        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={"format": "csv", "resource": "invalid_resource"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_export_missing_format_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that missing format field returns validation error."""
        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={"resource": "issues"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_export_missing_resource_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that missing resource field returns validation error."""
        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={"format": "csv"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_export_requires_auth(
        self,
        client: AsyncClient,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that creating an export requires authentication."""
        response = await client.post(
            f"/projects/{test_project_id}/exports",
            json={"format": "csv", "resource": "issues"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_export_project_not_found_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that creating an export for non-existent project returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        random_id = uuid.uuid4()
        response = await client.post(
            f"/projects/{random_id}/exports",
            headers=auth_headers,
            json={"format": "csv", "resource": "issues"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_export_other_users_project_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        other_user_project: MagicMock,
    ) -> None:
        """Test that creating an export for another user's project returns 404."""
        # Query will not find the project because it filters by owner_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            f"/projects/{other_user_project.id}/exports",
            headers=auth_headers,
            json={"format": "csv", "resource": "issues"},
        )

        assert response.status_code == 404


class TestListExports:
    """Tests for the GET /projects/{project_id}/exports endpoint."""

    @pytest.mark.asyncio
    async def test_list_exports_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that listing exports returns 200 OK."""
        # First call: get project
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        # Second call: count exports
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        # Third call: get exports
        mock_exports_result = MagicMock()
        mock_exports_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_count_result, mock_exports_result]
        )

        response = await client.get(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_exports_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that listing exports when none exist returns empty list."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_exports_result = MagicMock()
        mock_exports_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_count_result, mock_exports_result]
        )

        response = await client.get(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
        )

        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    @pytest.mark.asyncio
    async def test_list_exports_returns_exports(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that listing exports returns export records."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        # Create mock exports
        export1 = MagicMock()
        export1.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        export1.project_id = test_project_id
        export1.format = "csv"
        export1.resource = "issues"
        export1.status = "completed"
        export1.params = {}
        export1.artifact_key = "exports/test.csv"
        export1.file_size_bytes = 1024
        export1.download_url = "https://example.com/test.csv"
        export1.download_expires_at = datetime.now(UTC) + timedelta(days=7)
        export1.error_message = None
        export1.started_at = datetime.now(UTC) - timedelta(hours=1)
        export1.completed_at = datetime.now(UTC)
        export1.created_at = datetime.now(UTC) - timedelta(hours=2)

        export2 = MagicMock()
        export2.id = uuid.UUID("22222222-2222-2222-2222-222222222222")
        export2.project_id = test_project_id
        export2.format = "json"
        export2.resource = "backlinks"
        export2.status = "queued"
        export2.params = {}
        export2.artifact_key = None
        export2.file_size_bytes = None
        export2.download_url = None
        export2.download_expires_at = None
        export2.error_message = None
        export2.started_at = None
        export2.completed_at = None
        export2.created_at = datetime.now(UTC)

        mock_exports_result = MagicMock()
        mock_exports_result.scalars.return_value.all.return_value = [export1, export2]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_count_result, mock_exports_result]
        )

        response = await client.get(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
        )

        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["items"][0]["format"] == "csv"
        assert data["items"][0]["resource"] == "issues"
        assert data["items"][0]["status"] == "completed"
        assert data["items"][1]["format"] == "json"
        assert data["items"][1]["resource"] == "backlinks"
        assert data["items"][1]["status"] == "queued"

    @pytest.mark.asyncio
    async def test_list_exports_pagination(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that pagination parameters work correctly."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 50

        mock_exports_result = MagicMock()
        mock_exports_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_count_result, mock_exports_result]
        )

        response = await client.get(
            f"/projects/{test_project_id}/exports?page=2&pageSize=10",
            headers=auth_headers,
        )

        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert data["total"] == 50

    @pytest.mark.asyncio
    async def test_list_exports_requires_auth(
        self,
        client: AsyncClient,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that listing exports requires authentication."""
        response = await client.get(f"/projects/{test_project_id}/exports")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_exports_project_not_found_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that listing exports for non-existent project returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        random_id = uuid.uuid4()
        response = await client.get(
            f"/projects/{random_id}/exports",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_exports_other_users_project_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        other_user_project: MagicMock,
    ) -> None:
        """Test that listing exports for another user's project returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            f"/projects/{other_user_project.id}/exports",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestGetExportStatus:
    """Tests for the GET /projects/{project_id}/exports/{export_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_export_status_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting export status returns 200 OK."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export = MagicMock()
        mock_export.id = export_id
        mock_export.project_id = test_project_id
        mock_export.format = "csv"
        mock_export.resource = "issues"
        mock_export.status = "queued"
        mock_export.params = {}
        mock_export.artifact_key = None
        mock_export.file_size_bytes = None
        mock_export.download_url = None
        mock_export.download_expires_at = None
        mock_export.error_message = None
        mock_export.started_at = None
        mock_export.completed_at = None
        mock_export.created_at = datetime.now(UTC)
        mock_export.is_completed = False

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = mock_export

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_export_status_queued(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that queued export shows progress as 0."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export = MagicMock()
        mock_export.id = export_id
        mock_export.status = "queued"
        mock_export.error_message = None
        mock_export.started_at = None
        mock_export.completed_at = None
        mock_export.download_url = None
        mock_export.is_completed = False

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = mock_export

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}",
            headers=auth_headers,
        )

        data = response.json()
        assert data["status"] == "queued"
        assert data["progress"] == 0.0

    @pytest.mark.asyncio
    async def test_get_export_status_running(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that running export shows progress as 50."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export = MagicMock()
        mock_export.id = export_id
        mock_export.status = "running"
        mock_export.error_message = None
        mock_export.started_at = datetime.now(UTC) - timedelta(minutes=5)
        mock_export.completed_at = None
        mock_export.download_url = None
        mock_export.is_completed = False

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = mock_export

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}",
            headers=auth_headers,
        )

        data = response.json()
        assert data["status"] == "running"
        assert data["progress"] == 50.0

    @pytest.mark.asyncio
    async def test_get_export_status_completed(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that completed export shows progress as 100 and download URL."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        download_url = "https://example.com/exports/test.csv"

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export = MagicMock()
        mock_export.id = export_id
        mock_export.status = "completed"
        mock_export.error_message = None
        mock_export.started_at = datetime.now(UTC) - timedelta(hours=1)
        mock_export.completed_at = datetime.now(UTC)
        mock_export.download_url = download_url
        mock_export.is_completed = True

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = mock_export

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}",
            headers=auth_headers,
        )

        data = response.json()
        assert data["status"] == "completed"
        assert data["progress"] == 100.0
        assert data["download_url"] == download_url

    @pytest.mark.asyncio
    async def test_get_export_status_failed(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that failed export shows error message and no progress."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        error_message = "Database connection failed"

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export = MagicMock()
        mock_export.id = export_id
        mock_export.status = "failed"
        mock_export.error_message = error_message
        mock_export.started_at = datetime.now(UTC) - timedelta(hours=1)
        mock_export.completed_at = datetime.now(UTC)
        mock_export.download_url = None
        mock_export.is_completed = False

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = mock_export

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}",
            headers=auth_headers,
        )

        data = response.json()
        assert data["status"] == "failed"
        assert data["progress"] is None
        assert data["error_message"] == error_message

    @pytest.mark.asyncio
    async def test_get_export_status_requires_auth(
        self,
        client: AsyncClient,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting export status requires authentication."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_export_status_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting non-existent export returns 404."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        random_export_id = uuid.uuid4()
        response = await client.get(
            f"/projects/{test_project_id}/exports/{random_export_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestGetDownloadURL:
    """Tests for the GET /projects/{project_id}/exports/{export_id}/download endpoint."""

    @pytest.mark.asyncio
    async def test_get_download_url_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting download URL for completed export returns 200."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        download_url = "https://example.com/exports/test.csv"
        expires_at = datetime.now(UTC) + timedelta(days=7)

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export = MagicMock()
        mock_export.id = export_id
        mock_export.format = "csv"
        mock_export.status = "completed"
        mock_export.artifact_key = "exports/test.csv"
        mock_export.file_size_bytes = 1024
        mock_export.download_url = download_url
        mock_export.download_expires_at = expires_at

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = mock_export

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_download_url_returns_url_info(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting download URL returns URL, expiry, and content type."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        download_url = "https://example.com/exports/test.csv"
        expires_at = datetime.now(UTC) + timedelta(days=7)

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export = MagicMock()
        mock_export.id = export_id
        mock_export.format = "csv"
        mock_export.status = "completed"
        mock_export.artifact_key = "exports/test.csv"
        mock_export.file_size_bytes = 1024
        mock_export.download_url = download_url
        mock_export.download_expires_at = expires_at

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = mock_export

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}/download",
            headers=auth_headers,
        )

        data = response.json()
        assert data["export_id"] == str(export_id)
        assert data["download_url"] == download_url
        assert "expires_at" in data
        assert data["file_size_bytes"] == 1024
        assert data["content_type"] == "text/csv; charset=utf-8"

    @pytest.mark.asyncio
    async def test_get_download_url_json_content_type(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that JSON export returns correct content type."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        download_url = "https://example.com/exports/test.json"
        expires_at = datetime.now(UTC) + timedelta(days=7)

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export = MagicMock()
        mock_export.id = export_id
        mock_export.format = "json"
        mock_export.status = "completed"
        mock_export.artifact_key = "exports/test.json"
        mock_export.file_size_bytes = 2048
        mock_export.download_url = download_url
        mock_export.download_expires_at = expires_at

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = mock_export

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}/download",
            headers=auth_headers,
        )

        data = response.json()
        assert data["content_type"] == "application/json; charset=utf-8"

    @pytest.mark.asyncio
    async def test_get_download_url_not_completed_returns_409(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting download URL for non-completed export returns 409."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export = MagicMock()
        mock_export.id = export_id
        mock_export.status = "queued"

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = mock_export

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_get_download_url_running_returns_409(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting download URL for running export returns 409."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export = MagicMock()
        mock_export.id = export_id
        mock_export.status = "running"

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = mock_export

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_get_download_url_failed_returns_409(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting download URL for failed export returns 409."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export = MagicMock()
        mock_export.id = export_id
        mock_export.status = "failed"

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = mock_export

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_get_download_url_requires_auth(
        self,
        client: AsyncClient,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting download URL requires authentication."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}/download",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_download_url_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting download URL for non-existent export returns 404."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        random_export_id = uuid.uuid4()
        response = await client.get(
            f"/projects/{test_project_id}/exports/{random_export_id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestExportStatusTransitions:
    """Tests for export status state transitions."""

    @pytest.mark.asyncio
    async def test_export_created_with_queued_status(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that newly created export has queued status."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
            obj.project_id = test_project_id
            obj.format = "csv"
            obj.resource = "issues"
            obj.status = "queued"
            obj.params = {}
            obj.artifact_key = None
            obj.file_size_bytes = None
            obj.download_url = None
            obj.download_expires_at = None
            obj.error_message = None
            obj.started_at = None
            obj.completed_at = None
            obj.created_at = datetime.now(UTC)

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={"format": "csv", "resource": "issues"},
        )

        data = response.json()
        assert data["status"] == "queued"
        assert data["started_at"] is None
        assert data["completed_at"] is None
        assert data["download_url"] is None

    @pytest.mark.asyncio
    async def test_completed_export_has_timestamps(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that completed export has started_at and completed_at."""
        export_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        started_at = datetime.now(UTC) - timedelta(hours=1)
        completed_at = datetime.now(UTC)

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_export = MagicMock()
        mock_export.id = export_id
        mock_export.status = "completed"
        mock_export.error_message = None
        mock_export.started_at = started_at
        mock_export.completed_at = completed_at
        mock_export.download_url = "https://example.com/test.csv"
        mock_export.is_completed = True

        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = mock_export

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_export_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/{export_id}",
            headers=auth_headers,
        )

        data = response.json()
        assert data["started_at"] is not None
        assert data["completed_at"] is not None


class TestExportResources:
    """Tests for different export resource types."""

    @pytest.mark.asyncio
    async def test_export_issues_resource(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that issues resource is accepted."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
            obj.project_id = test_project_id
            obj.format = "csv"
            obj.resource = "issues"
            obj.status = "queued"
            obj.params = {}
            obj.artifact_key = None
            obj.file_size_bytes = None
            obj.download_url = None
            obj.download_expires_at = None
            obj.error_message = None
            obj.started_at = None
            obj.completed_at = None
            obj.created_at = datetime.now(UTC)

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={"format": "csv", "resource": "issues"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["resource"] == "issues"

    @pytest.mark.asyncio
    async def test_export_backlinks_resource(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that backlinks resource is accepted."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
            obj.project_id = test_project_id
            obj.format = "csv"
            obj.resource = "backlinks"
            obj.status = "queued"
            obj.params = {}
            obj.artifact_key = None
            obj.file_size_bytes = None
            obj.download_url = None
            obj.download_expires_at = None
            obj.error_message = None
            obj.started_at = None
            obj.completed_at = None
            obj.created_at = datetime.now(UTC)

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={"format": "csv", "resource": "backlinks"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["resource"] == "backlinks"

    @pytest.mark.asyncio
    async def test_export_pages_resource(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that pages resource is accepted."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
            obj.project_id = test_project_id
            obj.format = "json"
            obj.resource = "pages"
            obj.status = "queued"
            obj.params = {"crawl_run_id": "some-id"}
            obj.artifact_key = None
            obj.file_size_bytes = None
            obj.download_url = None
            obj.download_expires_at = None
            obj.error_message = None
            obj.started_at = None
            obj.completed_at = None
            obj.created_at = datetime.now(UTC)

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={
                "format": "json",
                "resource": "pages",
                "params": {"crawl_run_id": "some-id"},
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["resource"] == "pages"

    @pytest.mark.asyncio
    async def test_export_performance_resource(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that performance resource is accepted."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
            obj.project_id = test_project_id
            obj.format = "csv"
            obj.resource = "performance"
            obj.status = "queued"
            obj.params = {}
            obj.artifact_key = None
            obj.file_size_bytes = None
            obj.download_url = None
            obj.download_expires_at = None
            obj.error_message = None
            obj.started_at = None
            obj.completed_at = None
            obj.created_at = datetime.now(UTC)

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={"format": "csv", "resource": "performance"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["resource"] == "performance"

    @pytest.mark.asyncio
    async def test_export_full_report_resource(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that full_report resource is accepted."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
            obj.project_id = test_project_id
            obj.format = "json"
            obj.resource = "full_report"
            obj.status = "queued"
            obj.params = {}
            obj.artifact_key = None
            obj.file_size_bytes = None
            obj.download_url = None
            obj.download_expires_at = None
            obj.error_message = None
            obj.started_at = None
            obj.completed_at = None
            obj.created_at = datetime.now(UTC)

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project_id}/exports",
            headers=auth_headers,
            json={"format": "json", "resource": "full_report"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["resource"] == "full_report"
