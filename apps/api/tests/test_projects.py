"""
Tests for Projects CRUD endpoints.

Tests cover:
- Project listing (pagination, user isolation)
- Project creation (validation, auth)
- Project retrieval (ownership, not found)
- Project update (partial updates)
- Project deletion
- Site management
- Competitor management
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from semrush_core.models import Project, Site, Competitor


class TestProjectsCRUD:
    """Test suite for project CRUD operations."""

    # =========================================================================
    # List Projects
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_projects_empty(
        self, client, auth_headers, mock_db_session, test_user_id
    ):
        """Should return empty list when user has no projects."""
        # Setup: Return empty results from database
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_count_result, mock_result]
        )

        response = await client.get("/projects", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    @pytest.mark.asyncio
    async def test_list_projects_returns_user_projects_only(
        self,
        client,
        auth_headers,
        mock_db_session,
        test_user_id,
        test_project,
        other_user_project,
    ):
        """Should only return projects owned by the authenticated user."""
        # Setup: Return only test_project (not other_user_project)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [test_project]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_count_result, mock_result]
        )

        response = await client.get("/projects", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(test_project.id)
        assert data["items"][0]["name"] == "Test Project"
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_projects_pagination(
        self, client, auth_headers, mock_db_session, test_user_id
    ):
        """Should respect pagination parameters."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 50

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_count_result, mock_result]
        )

        response = await client.get(
            "/projects?page=2&pageSize=10", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert data["total"] == 50

    @pytest.mark.asyncio
    async def test_list_projects_requires_auth(self, client):
        """Should require authentication to list projects."""
        response = await client.get("/projects")
        assert response.status_code == 401

    # =========================================================================
    # Create Project
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_project_success(
        self, client, auth_headers, mock_db_session, test_user_id
    ):
        """Should create a new project with valid data."""
        # Setup mock to capture the project being created
        created_project = MagicMock()
        created_project.id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        created_project.owner_id = test_user_id
        created_project.name = "My SEO Project"
        created_project.created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        created_project.updated_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock(return_value=created_project)

        # Make refresh set the attributes we expect
        async def mock_refresh(obj):
            obj.id = created_project.id
            obj.created_at = created_project.created_at
            obj.updated_at = created_project.updated_at

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            "/projects", headers=auth_headers, json={"name": "My SEO Project"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My SEO Project"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_create_project_empty_name_fails(self, client, auth_headers):
        """Should reject empty project name."""
        response = await client.post(
            "/projects", headers=auth_headers, json={"name": ""}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_project_name_too_long_fails(self, client, auth_headers):
        """Should reject project name exceeding max length."""
        response = await client.post(
            "/projects", headers=auth_headers, json={"name": "a" * 256}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_project_requires_auth(self, client):
        """Should require authentication to create a project."""
        response = await client.post("/projects", json={"name": "Test"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_project_missing_name_fails(self, client, auth_headers):
        """Should reject request without name field."""
        response = await client.post("/projects", headers=auth_headers, json={})
        assert response.status_code == 422

    # =========================================================================
    # Get Project
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_project_success(
        self, client, auth_headers, mock_db_session, test_project, test_user_id
    ):
        """Should return project when user owns it."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            f"/projects/{test_project.id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_project.id)
        assert data["name"] == "Test Project"

    @pytest.mark.asyncio
    async def test_get_project_not_found(
        self, client, auth_headers, mock_db_session, test_user_id
    ):
        """Should return 404 for non-existent project."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        random_id = uuid.uuid4()
        response = await client.get(f"/projects/{random_id}", headers=auth_headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_other_users_project_returns_404(
        self, client, auth_headers, mock_db_session, other_user_project, test_user_id
    ):
        """Should return 404 for project owned by another user (security)."""
        # The query will not find the project since it filters by owner_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            f"/projects/{other_user_project.id}", headers=auth_headers
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_project_requires_auth(self, client, test_project):
        """Should require authentication to get a project."""
        response = await client.get(f"/projects/{test_project.id}")
        assert response.status_code == 401

    # =========================================================================
    # Update Project
    # =========================================================================

    @pytest.mark.asyncio
    async def test_update_project_success(
        self, client, auth_headers, mock_db_session, test_project, test_user_id
    ):
        """Should update project name successfully."""
        # Setup: Find project
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        response = await client.patch(
            f"/projects/{test_project.id}",
            headers=auth_headers,
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_project_partial(
        self, client, auth_headers, mock_db_session, test_project, test_user_id
    ):
        """Should allow PATCH with empty body (no-op update)."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        response = await client.patch(
            f"/projects/{test_project.id}", headers=auth_headers, json={}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_project_not_found(
        self, client, auth_headers, mock_db_session, test_user_id
    ):
        """Should return 404 for non-existent project."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        random_id = uuid.uuid4()
        response = await client.patch(
            f"/projects/{random_id}", headers=auth_headers, json={"name": "New Name"}
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_other_users_project_returns_404(
        self, client, auth_headers, mock_db_session, other_user_project, test_user_id
    ):
        """Should return 404 for project owned by another user."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.patch(
            f"/projects/{other_user_project.id}",
            headers=auth_headers,
            json={"name": "Hacked"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_project_requires_auth(self, client, test_project):
        """Should require authentication to update a project."""
        response = await client.patch(
            f"/projects/{test_project.id}", json={"name": "Updated"}
        )
        assert response.status_code == 401

    # =========================================================================
    # Delete Project
    # =========================================================================

    @pytest.mark.asyncio
    async def test_delete_project_success(
        self, client, auth_headers, mock_db_session, test_project, test_user_id
    ):
        """Should delete project successfully."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()
        mock_db_session.commit = AsyncMock()

        response = await client.delete(
            f"/projects/{test_project.id}", headers=auth_headers
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_project_not_found(
        self, client, auth_headers, mock_db_session, test_user_id
    ):
        """Should return 404 for non-existent project."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        random_id = uuid.uuid4()
        response = await client.delete(f"/projects/{random_id}", headers=auth_headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_project_returns_404(
        self, client, auth_headers, mock_db_session, other_user_project, test_user_id
    ):
        """Should return 404 for project owned by another user."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.delete(
            f"/projects/{other_user_project.id}", headers=auth_headers
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project_requires_auth(self, client, test_project):
        """Should require authentication to delete a project."""
        response = await client.delete(f"/projects/{test_project.id}")
        assert response.status_code == 401


class TestSites:
    """Test suite for site management within projects."""

    @pytest.mark.asyncio
    async def test_add_site_to_project(
        self, client, auth_headers, mock_db_session, test_project, test_user_id
    ):
        """Should add a site to a project."""
        # Setup: Project exists and is owned by user
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        created_site = MagicMock()
        created_site.id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
        created_site.project_id = test_project.id
        created_site.domain = "example.com"
        created_site.base_url = "https://example.com"
        created_site.created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.id = created_site.id
            obj.project_id = created_site.project_id
            obj.domain = created_site.domain
            obj.base_url = created_site.base_url
            obj.created_at = created_site.created_at

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project.id}/sites",
            headers=auth_headers,
            json={"domain": "example.com", "base_url": "https://example.com"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["domain"] == "example.com"
        assert data["base_url"] == "https://example.com"
        assert data["project_id"] == str(test_project.id)

    @pytest.mark.asyncio
    async def test_add_site_invalid_url(
        self, client, auth_headers, mock_db_session, test_project, test_user_id
    ):
        """Should reject site with invalid base_url."""
        response = await client.post(
            f"/projects/{test_project.id}/sites",
            headers=auth_headers,
            json={"domain": "example.com", "base_url": "not-a-url"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_add_site_project_not_found(
        self, client, auth_headers, mock_db_session, test_user_id
    ):
        """Should return 404 for non-existent project."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        random_id = uuid.uuid4()
        response = await client.post(
            f"/projects/{random_id}/sites",
            headers=auth_headers,
            json={"domain": "example.com", "base_url": "https://example.com"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_add_site_to_other_users_project_returns_404(
        self, client, auth_headers, mock_db_session, other_user_project, test_user_id
    ):
        """Should return 404 for project owned by another user."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            f"/projects/{other_user_project.id}/sites",
            headers=auth_headers,
            json={"domain": "example.com", "base_url": "https://example.com"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_add_site_requires_auth(self, client, test_project):
        """Should require authentication to add a site."""
        response = await client.post(
            f"/projects/{test_project.id}/sites",
            json={"domain": "example.com", "base_url": "https://example.com"},
        )
        assert response.status_code == 401


class TestCompetitors:
    """Test suite for competitor management within projects."""

    @pytest.mark.asyncio
    async def test_add_competitor(
        self, client, auth_headers, mock_db_session, test_project, test_user_id
    ):
        """Should add a competitor to a project."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        created_competitor = MagicMock()
        created_competitor.id = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
        created_competitor.project_id = test_project.id
        created_competitor.domain = "competitor.com"
        created_competitor.created_at = datetime(
            2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc
        )

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.id = created_competitor.id
            obj.project_id = created_competitor.project_id
            obj.domain = created_competitor.domain
            obj.created_at = created_competitor.created_at

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project.id}/competitors",
            headers=auth_headers,
            json={"domain": "competitor.com"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["domain"] == "competitor.com"
        assert data["project_id"] == str(test_project.id)

    @pytest.mark.asyncio
    async def test_add_competitor_empty_domain_fails(
        self, client, auth_headers, test_project
    ):
        """Should reject competitor with empty domain."""
        response = await client.post(
            f"/projects/{test_project.id}/competitors",
            headers=auth_headers,
            json={"domain": ""},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_add_competitor_project_not_found(
        self, client, auth_headers, mock_db_session, test_user_id
    ):
        """Should return 404 for non-existent project."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        random_id = uuid.uuid4()
        response = await client.post(
            f"/projects/{random_id}/competitors",
            headers=auth_headers,
            json={"domain": "competitor.com"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_add_competitor_requires_auth(self, client, test_project):
        """Should require authentication to add a competitor."""
        response = await client.post(
            f"/projects/{test_project.id}/competitors",
            json={"domain": "competitor.com"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_competitors(
        self,
        client,
        auth_headers,
        mock_db_session,
        test_project,
        test_competitors,
        test_user_id,
    ):
        """Should list all competitors for a project."""
        # First call: get project
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        # Second call: get competitors
        mock_competitors_result = MagicMock()
        mock_competitors_result.scalars.return_value.all.return_value = test_competitors

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_competitors_result]
        )

        response = await client.get(
            f"/projects/{test_project.id}/competitors", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["domain"] == "competitor1.com"
        assert data["items"][1]["domain"] == "competitor2.com"

    @pytest.mark.asyncio
    async def test_list_competitors_empty(
        self, client, auth_headers, mock_db_session, test_project, test_user_id
    ):
        """Should return empty list when no competitors."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_competitors_result = MagicMock()
        mock_competitors_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_competitors_result]
        )

        response = await client.get(
            f"/projects/{test_project.id}/competitors", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_competitors_project_not_found(
        self, client, auth_headers, mock_db_session, test_user_id
    ):
        """Should return 404 for non-existent project."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        random_id = uuid.uuid4()
        response = await client.get(
            f"/projects/{random_id}/competitors", headers=auth_headers
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_competitors_requires_auth(self, client, test_project):
        """Should require authentication to list competitors."""
        response = await client.get(f"/projects/{test_project.id}/competitors")
        assert response.status_code == 401
