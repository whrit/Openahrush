"""
Project Settings endpoint tests following TDD (Red-Green-Refactor).

Tests cover:
- GET /projects/{project_id}/settings - Retrieve project settings with defaults
- PUT /projects/{project_id}/settings - Update project settings with validation

Tests validate:
- Authentication requirements
- Authorization (project ownership)
- Default values for new projects
- Full and partial updates
- Input validation (URLs, regexes, ranges, enums)
- Error responses (401, 404, 422)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


class TestGetProjectSettings:
    """Tests for GET /projects/{project_id}/settings endpoint."""

    @pytest.mark.asyncio
    async def test_get_settings_new_project_returns_defaults(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that getting settings for a new project returns default values.

        A project without explicitly configured settings should return sensible defaults.
        """
        # Mock project lookup - project exists, belongs to user
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        # Mock settings lookup - no settings exist yet
        mock_settings_result = MagicMock()
        mock_settings_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_settings_result]
        )

        response = await client.get(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify default values
        assert data["max_pages"] == 5000
        assert data["max_depth"] == 6
        assert data["js_render_mode"] == "hybrid"
        assert data["audit_frequency"] == "weekly"
        assert data["include_subdomains"] is True
        assert data["respect_robots"] is True
        assert data["retain_audit_runs"] == 10

    @pytest.mark.asyncio
    async def test_get_settings_requires_auth(
        self,
        client: AsyncClient,
        test_project: MagicMock,
    ) -> None:
        """
        Test that getting settings without authentication returns 401.

        The endpoint requires a valid JWT token.
        """
        response = await client.get(f"/projects/{test_project.id}/settings")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_settings_nonexistent_project_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that getting settings for a non-existent project returns 404.

        Unknown project IDs should return not found error.
        """
        # Mock project lookup - project does not exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        random_uuid = uuid.uuid4()
        response = await client.get(
            f"/projects/{random_uuid}/settings",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_settings_wrong_owner_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that getting settings for another user's project returns 404.

        Users should only see their own projects.
        """
        # Create project owned by different user
        other_user_project = MagicMock()
        other_user_project.id = uuid.uuid4()
        other_user_project.owner_id = uuid.uuid4()  # Different owner
        other_user_project.name = "Other Project"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = other_user_project
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            f"/projects/{other_user_project.id}/settings",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_settings_returns_saved_values(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that getting settings returns previously saved values.

        Custom settings should override defaults.
        """
        # Mock settings with custom values
        mock_settings = MagicMock()
        mock_settings.settings = {
            "seed_url": "https://mysite.com",
            "max_pages": 10000,
            "js_render_mode": "off",
            "audit_frequency": "daily",
        }

        # First call returns project, second call returns settings
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_settings_result = MagicMock()
        mock_settings_result.scalar_one_or_none.return_value = mock_settings

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_settings_result]
        )

        response = await client.get(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["seed_url"] == "https://mysite.com"
        assert data["max_pages"] == 10000
        assert data["js_render_mode"] == "off"
        assert data["audit_frequency"] == "daily"

    @pytest.mark.asyncio
    async def test_get_settings_invalid_uuid_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """
        Test that an invalid UUID in the path returns 422.
        """
        response = await client.get(
            "/projects/not-a-uuid/settings",
            headers=auth_headers,
        )

        assert response.status_code == 422


class TestUpdateProjectSettings:
    """Tests for PUT /projects/{project_id}/settings endpoint."""

    @pytest.mark.asyncio
    async def test_update_settings_full_replace(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that updating settings replaces values completely.

        PUT should update the entire settings object.
        """
        # Mock project exists and belongs to user
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        new_settings = {
            "seed_url": "https://mysite.com",
            "max_pages": 10000,
            "js_render_mode": "off",
            "audit_frequency": "daily",
        }

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json=new_settings,
        )

        assert response.status_code == 200
        assert response.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_update_settings_requires_auth(
        self,
        client: AsyncClient,
        test_project: MagicMock,
    ) -> None:
        """
        Test that updating settings without authentication returns 401.
        """
        response = await client.put(
            f"/projects/{test_project.id}/settings",
            json={"seed_url": "https://example.com"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_settings_nonexistent_project_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that updating settings for non-existent project returns 404.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        random_uuid = uuid.uuid4()
        response = await client.put(
            f"/projects/{random_uuid}/settings",
            headers=auth_headers,
            json={"seed_url": "https://example.com"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_settings_wrong_owner_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """
        Test that updating another user's project returns 404.
        """
        other_user_project = MagicMock()
        other_user_project.id = uuid.uuid4()
        other_user_project.owner_id = uuid.uuid4()  # Different owner

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = other_user_project
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.put(
            f"/projects/{other_user_project.id}/settings",
            headers=auth_headers,
            json={"seed_url": "https://example.com"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_settings_invalid_seed_url_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that an invalid seed_url returns 422 validation error.

        seed_url must start with http:// or https://.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={"seed_url": "not-a-valid-url"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_settings_invalid_regex_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that invalid regex patterns return 422 validation error.

        include_regexes and exclude_regexes must contain valid regex patterns.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "include_regexes": ["[invalid(regex"],
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_settings_max_pages_out_of_range_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that max_pages outside valid range returns 422.

        max_pages must be between 1 and 100000.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "max_pages": 999999,  # Too high
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_settings_max_pages_zero_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that max_pages of zero returns 422.

        max_pages must be at least 1.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "max_pages": 0,
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_settings_invalid_js_mode_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that invalid js_render_mode returns 422.

        js_render_mode must be one of: off, hybrid, js_only.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "js_render_mode": "invalid_mode",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_settings_invalid_audit_frequency_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that invalid audit_frequency returns 422.

        audit_frequency must be one of: off, daily, weekly.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "audit_frequency": "hourly",  # Not a valid option
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_settings_empty_selector_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that empty CSS selectors return 422.

        required_selectors cannot contain empty strings.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "required_selectors": ["div.content", "   "],  # Empty after strip
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_settings_extra_fields_rejected(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that unknown fields are rejected.

        Schema has extra="forbid" so unknown fields should fail.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "unknown_field": "should_be_rejected",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_settings_max_depth_boundaries(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test max_depth boundary validation.

        max_depth must be between 1 and 20.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        # Test too high
        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "max_depth": 21,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_settings_concurrency_html_boundaries(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test concurrency_html boundary validation.

        concurrency_html must be between 1 and 100.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "concurrency_html": 101,  # Too high
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_settings_valid_all_fields(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test updating all settings fields with valid values.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        full_settings = {
            "seed_url": "https://mysite.com",
            "include_subdomains": False,
            "allowed_hosts": ["cdn.mysite.com", "api.mysite.com"],
            "allowed_schemes": ["https"],
            "include_regexes": [r"^/blog/.*", r"^/products/\d+$"],
            "exclude_regexes": [r"^/admin/.*"],
            "query_param_policy": "allowlist",
            "query_param_allowlist": ["page", "sort"],
            "query_param_denylist": [],
            "strip_tracking_params": True,
            "max_pages": 10000,
            "max_depth": 10,
            "concurrency_html": 32,
            "politeness_delay_ms": 100,
            "respect_robots": True,
            "use_sitemaps": True,
            "user_agent": "MyCustomBot/1.0",
            "js_render_mode": "hybrid",
            "max_rendered_pages": 500,
            "max_render_time_ms": 20000,
            "concurrency_js": 4,
            "required_selectors": ["main", "article"],
            "audit_frequency": "daily",
            "integration_sync_frequency": "weekly",
            "visibility_refresh_frequency": "weekly",
            "links_refresh_frequency": "off",
            "retain_audit_runs": 20,
            "retain_serp_snapshots_days": 180,
            "retain_raw_html_days": 30,
        }

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json=full_settings,
        )

        assert response.status_code == 200
        assert response.json()["ok"] is True


class TestSettingsSchemaValidation:
    """Tests for schema validation edge cases."""

    @pytest.mark.asyncio
    async def test_seed_url_with_path(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that seed_url with path is accepted.

        Users may want to start crawling from a subpath.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={"seed_url": "https://example.com/blog/"},
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_http_seed_url_accepted(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that http:// URLs are accepted (not just https://).

        Some sites may not have SSL configured.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={"seed_url": "http://example.com"},
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_complex_valid_regex(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that complex but valid regex patterns are accepted.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "include_regexes": [
                    r"^/products/[a-z0-9-]+/reviews$",
                    r"^/category/(?:electronics|clothing)/.*",
                ],
            },
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_min_valid_values(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test minimum valid values for numeric fields.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "max_pages": 1,
                "max_depth": 1,
                "concurrency_html": 1,
                "politeness_delay_ms": 0,
                "max_rendered_pages": 0,
                "max_render_time_ms": 1000,
                "concurrency_js": 1,
                "retain_audit_runs": 1,
                "retain_serp_snapshots_days": 0,
                "retain_raw_html_days": 0,
            },
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_max_valid_values(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test maximum valid values for numeric fields.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "max_pages": 100000,
                "max_depth": 20,
                "concurrency_html": 100,
                "politeness_delay_ms": 10000,
                "max_rendered_pages": 10000,
                "max_render_time_ms": 60000,
                "concurrency_js": 10,
                "retain_audit_runs": 100,
                "retain_serp_snapshots_days": 365,
                "retain_raw_html_days": 90,
            },
        )

        assert response.status_code == 200


class TestSettingsDataPersistence:
    """Tests for settings data persistence behavior."""

    @pytest.mark.asyncio
    async def test_update_settings_persists_to_database(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that settings are persisted to the database.

        After PUT, the settings should be saved.
        """
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project
        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.put(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
            json={
                "seed_url": "https://mysite.com",
                "max_pages": 8000,
            },
        )

        assert response.status_code == 200

        # Verify commit was called
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_get_settings_merged_with_defaults(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
    ) -> None:
        """
        Test that saved settings are merged with defaults.

        Settings not explicitly set should use defaults.
        """
        # Mock settings with only some values set
        mock_settings = MagicMock()
        mock_settings.settings = {
            "seed_url": "https://mysite.com",
            "max_pages": 8000,
            # All other fields should use defaults
        }

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_settings_result = MagicMock()
        mock_settings_result.scalar_one_or_none.return_value = mock_settings

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_settings_result]
        )

        response = await client.get(
            f"/projects/{test_project.id}/settings",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Custom values
        assert data["seed_url"] == "https://mysite.com"
        assert data["max_pages"] == 8000

        # Default values for unset fields
        assert data["max_depth"] == 6
        assert data["js_render_mode"] == "hybrid"
