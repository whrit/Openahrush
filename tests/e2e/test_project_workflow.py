"""
E2E tests for project workflow.

Tests the complete workflow:
- Project creation
- Site creation
- Crawl triggering
- Issues retrieval
"""

import uuid

import pytest
from playwright.async_api import APIRequestContext

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
]


class TestProjectWorkflow:
    """Test the complete project workflow."""

    async def test_create_project(
        self,
        auth_context: APIRequestContext,
    ) -> None:
        """Test project creation."""
        project_name = f"E2E Test Project {uuid.uuid4()}"

        # Create project
        response = await auth_context.post(
            "/projects",
            data={"name": project_name},
        )

        assert response.status == 201
        data = await response.json()
        assert data["name"] == project_name
        assert "id" in data

        # Cleanup
        await auth_context.delete(f"/projects/{data['id']}")

    async def test_list_projects(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test listing projects."""
        response = await auth_context.get("/projects")

        assert response.status == 200
        data = await response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Find our test project
        project_ids = [p["id"] for p in data]
        assert test_project["id"] in project_ids

    async def test_get_project(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test getting a single project."""
        response = await auth_context.get(f"/projects/{test_project['id']}")

        assert response.status == 200
        data = await response.json()
        assert data["id"] == test_project["id"]
        assert data["name"] == test_project["name"]

    async def test_update_project(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test updating a project."""
        new_name = f"Updated Project {uuid.uuid4()}"

        response = await auth_context.patch(
            f"/projects/{test_project['id']}",
            data={"name": new_name},
        )

        assert response.status == 200
        data = await response.json()
        assert data["name"] == new_name

    async def test_create_site(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test site creation within a project."""
        site_url = "https://example.com"

        response = await auth_context.post(
            f"/projects/{test_project['id']}/sites",
            data={"url": site_url},
        )

        assert response.status == 201
        data = await response.json()
        assert data["url"] == site_url
        assert data["project_id"] == test_project["id"]

    async def test_list_project_sites(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test listing sites within a project."""
        # First create a site
        await auth_context.post(
            f"/projects/{test_project['id']}/sites",
            data={"url": "https://example.org"},
        )

        response = await auth_context.get(f"/projects/{test_project['id']}/sites")

        assert response.status == 200
        data = await response.json()
        assert isinstance(data, list)

    async def test_delete_project(
        self,
        auth_context: APIRequestContext,
    ) -> None:
        """Test project deletion."""
        # Create a project to delete
        create_response = await auth_context.post(
            "/projects",
            data={"name": f"Project to Delete {uuid.uuid4()}"},
        )
        project = await create_response.json()

        # Delete the project
        delete_response = await auth_context.delete(f"/projects/{project['id']}")
        assert delete_response.status == 204

        # Verify it's deleted
        get_response = await auth_context.get(f"/projects/{project['id']}")
        assert get_response.status == 404


class TestProjectValidation:
    """Test project input validation."""

    async def test_create_project_missing_name(
        self,
        auth_context: APIRequestContext,
    ) -> None:
        """Test that creating a project without a name fails."""
        response = await auth_context.post(
            "/projects",
            data={},
        )

        assert response.status == 422

    async def test_get_nonexistent_project(
        self,
        auth_context: APIRequestContext,
    ) -> None:
        """Test getting a nonexistent project returns 404."""
        fake_id = str(uuid.uuid4())
        response = await auth_context.get(f"/projects/{fake_id}")

        assert response.status == 404


class TestProjectAuthentication:
    """Test project authentication requirements."""

    async def test_list_projects_unauthenticated(
        self,
        api_context: APIRequestContext,
    ) -> None:
        """Test that listing projects without auth fails."""
        response = await api_context.get("/projects")

        assert response.status == 401

    async def test_create_project_unauthenticated(
        self,
        api_context: APIRequestContext,
    ) -> None:
        """Test that creating a project without auth fails."""
        response = await api_context.post(
            "/projects",
            data={"name": "Unauthorized Project"},
        )

        assert response.status == 401
