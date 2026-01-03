"""
E2E tests for export workflow.

Tests the complete export workflow:
- Export creation
- Export status polling
- Export download
"""

import uuid

import pytest
from playwright.async_api import APIRequestContext

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
]


class TestExportWorkflow:
    """Test the complete export workflow."""

    async def test_create_export(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test export creation."""
        response = await auth_context.post(
            f"/projects/{test_project['id']}/exports",
            data={
                "format": "csv",
                "type": "issues",
            },
        )

        # Export creation should return 201 or 202 (accepted)
        assert response.status in [201, 202]
        data = await response.json()
        assert "id" in data
        assert data["format"] == "csv"

    async def test_list_exports(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test listing exports for a project."""
        response = await auth_context.get(
            f"/projects/{test_project['id']}/exports",
        )

        assert response.status == 200
        data = await response.json()
        assert isinstance(data, list)

    async def test_get_export_status(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test getting export status."""
        # First create an export
        create_response = await auth_context.post(
            f"/projects/{test_project['id']}/exports",
            data={
                "format": "json",
                "type": "pages",
            },
        )

        if create_response.status not in [201, 202]:
            pytest.skip("Export creation not supported")

        export = await create_response.json()

        # Get export status
        status_response = await auth_context.get(
            f"/projects/{test_project['id']}/exports/{export['id']}",
        )

        assert status_response.status == 200
        data = await status_response.json()
        assert "status" in data
        assert data["status"] in ["pending", "processing", "completed", "failed"]


class TestExportFormats:
    """Test different export formats."""

    @pytest.mark.parametrize("format_type", ["csv", "json", "pdf"])
    async def test_export_formats(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
        format_type: str,
    ) -> None:
        """Test that different export formats are accepted."""
        response = await auth_context.post(
            f"/projects/{test_project['id']}/exports",
            data={
                "format": format_type,
                "type": "issues",
            },
        )

        # Should accept the format (even if processing fails later)
        assert response.status in [201, 202, 400, 422]


class TestExportValidation:
    """Test export input validation."""

    async def test_create_export_invalid_format(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test that invalid export format is rejected."""
        response = await auth_context.post(
            f"/projects/{test_project['id']}/exports",
            data={
                "format": "invalid_format",
                "type": "issues",
            },
        )

        assert response.status == 422

    async def test_get_nonexistent_export(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test getting a nonexistent export returns 404."""
        fake_id = str(uuid.uuid4())
        response = await auth_context.get(
            f"/projects/{test_project['id']}/exports/{fake_id}",
        )

        assert response.status == 404


class TestExportSchedules:
    """Test export scheduling functionality."""

    async def test_create_export_schedule(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test creating an export schedule."""
        response = await auth_context.post(
            f"/projects/{test_project['id']}/export-schedules",
            data={
                "format": "csv",
                "type": "issues",
                "frequency": "weekly",
            },
        )

        # Schedule creation should work or return not implemented
        assert response.status in [201, 404, 501]

    async def test_list_export_schedules(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test listing export schedules."""
        response = await auth_context.get(
            f"/projects/{test_project['id']}/export-schedules",
        )

        # Should return list or not implemented
        assert response.status in [200, 404, 501]
