"""
Tests for Export Schedule endpoints following TDD (Red-Green-Refactor).

Tests cover:
- POST /projects/{project_id}/exports/schedules - Create schedule
- GET /projects/{project_id}/exports/schedules - List schedules
- GET /projects/{project_id}/exports/schedules/{schedule_id} - Get schedule
- PATCH /projects/{project_id}/exports/schedules/{schedule_id} - Update schedule
- DELETE /projects/{project_id}/exports/schedules/{schedule_id} - Delete schedule
- Authorization (user can only access own project's schedules)
- Cron expression validation
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


class TestCreateSchedule:
    """Tests for the POST /projects/{project_id}/exports/schedules endpoint."""

    @pytest.mark.asyncio
    async def test_create_schedule_returns_201_created(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that creating a schedule returns 201 Created."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)

        async def mock_refresh(obj):
            obj.id = schedule_id
            obj.project_id = test_project_id
            obj.format = "csv"
            obj.resource = "issues"
            obj.cron_expression = "0 9 * * MON"
            obj.timezone = "UTC"
            obj.is_enabled = True
            obj.params = {}
            obj.last_run_at = None
            obj.next_run_at = datetime(2024, 1, 8, 9, 0, 0, tzinfo=UTC)
            obj.created_at = created_at

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project_id}/exports/schedules",
            headers=auth_headers,
            json={
                "format": "csv",
                "resource": "issues",
                "cron_expression": "0 9 * * MON",
            },
        )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_schedule_returns_schedule_record(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that creating a schedule returns the schedule record."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        next_run_at = datetime(2024, 1, 8, 9, 0, 0, tzinfo=UTC)

        async def mock_refresh(obj):
            obj.id = schedule_id
            obj.project_id = test_project_id
            obj.format = "json"
            obj.resource = "backlinks"
            obj.cron_expression = "0 0 * * *"
            obj.timezone = "America/New_York"
            obj.is_enabled = True
            obj.params = {"source_type": "commoncrawl"}
            obj.last_run_at = None
            obj.next_run_at = next_run_at
            obj.created_at = created_at

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.post(
            f"/projects/{test_project_id}/exports/schedules",
            headers=auth_headers,
            json={
                "format": "json",
                "resource": "backlinks",
                "cron_expression": "0 0 * * *",
                "timezone": "America/New_York",
                "params": {"source_type": "commoncrawl"},
            },
        )

        data = response.json()
        assert data["id"] == str(schedule_id)
        assert data["format"] == "json"
        assert data["resource"] == "backlinks"
        assert data["cron_expression"] == "0 0 * * *"
        assert data["timezone"] == "America/New_York"
        assert data["is_enabled"] is True
        assert data["last_run_at"] is None
        assert data["next_run_at"] is not None
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_schedule_with_invalid_cron_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that invalid cron expression returns 422 validation error."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        response = await client.post(
            f"/projects/{test_project_id}/exports/schedules",
            headers=auth_headers,
            json={
                "format": "csv",
                "resource": "issues",
                "cron_expression": "invalid cron",
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "cron" in str(data).lower() or "invalid" in str(data).lower()

    @pytest.mark.asyncio
    async def test_create_schedule_with_invalid_format_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that invalid format returns validation error."""
        response = await client.post(
            f"/projects/{test_project_id}/exports/schedules",
            headers=auth_headers,
            json={
                "format": "invalid_format",
                "resource": "issues",
                "cron_expression": "0 9 * * MON",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_schedule_with_invalid_resource_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that invalid resource returns validation error."""
        response = await client.post(
            f"/projects/{test_project_id}/exports/schedules",
            headers=auth_headers,
            json={
                "format": "csv",
                "resource": "invalid_resource",
                "cron_expression": "0 9 * * MON",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_schedule_requires_auth(
        self,
        client: AsyncClient,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that creating a schedule requires authentication."""
        response = await client.post(
            f"/projects/{test_project_id}/exports/schedules",
            json={
                "format": "csv",
                "resource": "issues",
                "cron_expression": "0 9 * * MON",
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_schedule_project_not_found_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that creating a schedule for non-existent project returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        random_id = uuid.uuid4()
        response = await client.post(
            f"/projects/{random_id}/exports/schedules",
            headers=auth_headers,
            json={
                "format": "csv",
                "resource": "issues",
                "cron_expression": "0 9 * * MON",
            },
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_schedule_other_users_project_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        other_user_project: MagicMock,
    ) -> None:
        """Test that creating a schedule for another user's project returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.post(
            f"/projects/{other_user_project.id}/exports/schedules",
            headers=auth_headers,
            json={
                "format": "csv",
                "resource": "issues",
                "cron_expression": "0 9 * * MON",
            },
        )

        assert response.status_code == 404


class TestListSchedules:
    """Tests for the GET /projects/{project_id}/exports/schedules endpoint."""

    @pytest.mark.asyncio
    async def test_list_schedules_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that listing schedules returns 200 OK."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_schedules_result = MagicMock()
        mock_schedules_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_count_result, mock_schedules_result]
        )

        response = await client.get(
            f"/projects/{test_project_id}/exports/schedules",
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_schedules_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that listing schedules when none exist returns empty list."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_schedules_result = MagicMock()
        mock_schedules_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_count_result, mock_schedules_result]
        )

        response = await client.get(
            f"/projects/{test_project_id}/exports/schedules",
            headers=auth_headers,
        )

        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_list_schedules_returns_schedules(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that listing schedules returns schedule records."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        # Create mock schedules
        schedule1 = MagicMock()
        schedule1.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        schedule1.project_id = test_project_id
        schedule1.format = "csv"
        schedule1.resource = "issues"
        schedule1.cron_expression = "0 9 * * MON"
        schedule1.timezone = "UTC"
        schedule1.is_enabled = True
        schedule1.params = {}
        schedule1.last_run_at = None
        schedule1.next_run_at = datetime.now(UTC) + timedelta(days=1)
        schedule1.created_at = datetime.now(UTC) - timedelta(days=7)

        schedule2 = MagicMock()
        schedule2.id = uuid.UUID("22222222-2222-2222-2222-222222222222")
        schedule2.project_id = test_project_id
        schedule2.format = "json"
        schedule2.resource = "backlinks"
        schedule2.cron_expression = "0 0 * * *"
        schedule2.timezone = "America/New_York"
        schedule2.is_enabled = False
        schedule2.params = {}
        schedule2.last_run_at = datetime.now(UTC) - timedelta(days=1)
        schedule2.next_run_at = None
        schedule2.created_at = datetime.now(UTC) - timedelta(days=3)

        mock_schedules_result = MagicMock()
        mock_schedules_result.scalars.return_value.all.return_value = [schedule1, schedule2]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_count_result, mock_schedules_result]
        )

        response = await client.get(
            f"/projects/{test_project_id}/exports/schedules",
            headers=auth_headers,
        )

        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["items"][0]["format"] == "csv"
        assert data["items"][0]["resource"] == "issues"
        assert data["items"][0]["cron_expression"] == "0 9 * * MON"
        assert data["items"][0]["is_enabled"] is True
        assert data["items"][1]["format"] == "json"
        assert data["items"][1]["resource"] == "backlinks"
        assert data["items"][1]["is_enabled"] is False

    @pytest.mark.asyncio
    async def test_list_schedules_pagination(
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

        mock_schedules_result = MagicMock()
        mock_schedules_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_project_result, mock_count_result, mock_schedules_result]
        )

        response = await client.get(
            f"/projects/{test_project_id}/exports/schedules?page=2&pageSize=10",
            headers=auth_headers,
        )

        data = response.json()
        assert data["page"] == 2
        assert data["total"] == 50

    @pytest.mark.asyncio
    async def test_list_schedules_requires_auth(
        self,
        client: AsyncClient,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that listing schedules requires authentication."""
        response = await client.get(f"/projects/{test_project_id}/exports/schedules")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_schedules_project_not_found_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that listing schedules for non-existent project returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        random_id = uuid.uuid4()
        response = await client.get(
            f"/projects/{random_id}/exports/schedules",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestGetSchedule:
    """Tests for the GET /projects/{project_id}/exports/schedules/{schedule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_schedule_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting a schedule returns 200 OK."""
        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_schedule = MagicMock()
        mock_schedule.id = schedule_id
        mock_schedule.project_id = test_project_id
        mock_schedule.format = "csv"
        mock_schedule.resource = "issues"
        mock_schedule.cron_expression = "0 9 * * MON"
        mock_schedule.timezone = "UTC"
        mock_schedule.is_enabled = True
        mock_schedule.params = {}
        mock_schedule.last_run_at = None
        mock_schedule.next_run_at = datetime.now(UTC) + timedelta(days=1)
        mock_schedule.created_at = datetime.now(UTC)

        mock_schedule_result = MagicMock()
        mock_schedule_result.scalar_one_or_none.return_value = mock_schedule

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_schedule_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/schedules/{schedule_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_schedule_returns_schedule_details(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting a schedule returns schedule details."""
        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_schedule = MagicMock()
        mock_schedule.id = schedule_id
        mock_schedule.project_id = test_project_id
        mock_schedule.format = "pdf"
        mock_schedule.resource = "full_report"
        mock_schedule.cron_expression = "0 6 1 * *"
        mock_schedule.timezone = "Europe/London"
        mock_schedule.is_enabled = True
        mock_schedule.params = {"include_charts": True}
        mock_schedule.last_run_at = datetime.now(UTC) - timedelta(days=30)
        mock_schedule.next_run_at = datetime.now(UTC) + timedelta(days=1)
        mock_schedule.created_at = datetime.now(UTC) - timedelta(days=60)

        mock_schedule_result = MagicMock()
        mock_schedule_result.scalar_one_or_none.return_value = mock_schedule

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_schedule_result])

        response = await client.get(
            f"/projects/{test_project_id}/exports/schedules/{schedule_id}",
            headers=auth_headers,
        )

        data = response.json()
        assert data["id"] == str(schedule_id)
        assert data["format"] == "pdf"
        assert data["resource"] == "full_report"
        assert data["cron_expression"] == "0 6 1 * *"
        assert data["timezone"] == "Europe/London"
        assert data["is_enabled"] is True
        assert data["last_run_at"] is not None
        assert data["next_run_at"] is not None
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_get_schedule_not_found_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting non-existent schedule returns 404."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_schedule_result = MagicMock()
        mock_schedule_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_schedule_result])

        random_schedule_id = uuid.uuid4()
        response = await client.get(
            f"/projects/{test_project_id}/exports/schedules/{random_schedule_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_schedule_requires_auth(
        self,
        client: AsyncClient,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that getting a schedule requires authentication."""
        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        response = await client.get(
            f"/projects/{test_project_id}/exports/schedules/{schedule_id}",
        )

        assert response.status_code == 401


class TestUpdateSchedule:
    """Tests for the PATCH /projects/{project_id}/exports/schedules/{schedule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_schedule_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that updating a schedule returns 200 OK."""
        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_schedule = MagicMock()
        mock_schedule.id = schedule_id
        mock_schedule.project_id = test_project_id
        mock_schedule.format = "csv"
        mock_schedule.resource = "issues"
        mock_schedule.cron_expression = "0 9 * * MON"
        mock_schedule.timezone = "UTC"
        mock_schedule.is_enabled = True
        mock_schedule.params = {}
        mock_schedule.last_run_at = None
        mock_schedule.next_run_at = datetime.now(UTC) + timedelta(days=1)
        mock_schedule.created_at = datetime.now(UTC)

        mock_schedule_result = MagicMock()
        mock_schedule_result.scalar_one_or_none.return_value = mock_schedule

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_schedule_result])
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        response = await client.patch(
            f"/projects/{test_project_id}/exports/schedules/{schedule_id}",
            headers=auth_headers,
            json={"is_enabled": False},
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_schedule_enable_disable(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that enabling/disabling a schedule works."""
        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_schedule = MagicMock()
        mock_schedule.id = schedule_id
        mock_schedule.project_id = test_project_id
        mock_schedule.format = "csv"
        mock_schedule.resource = "issues"
        mock_schedule.cron_expression = "0 9 * * MON"
        mock_schedule.timezone = "UTC"
        mock_schedule.is_enabled = True
        mock_schedule.params = {}
        mock_schedule.last_run_at = None
        mock_schedule.next_run_at = datetime.now(UTC) + timedelta(days=1)
        mock_schedule.created_at = datetime.now(UTC)

        mock_schedule_result = MagicMock()
        mock_schedule_result.scalar_one_or_none.return_value = mock_schedule

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_schedule_result])
        mock_db_session.commit = AsyncMock()

        async def mock_refresh(obj):
            obj.is_enabled = False
            obj.next_run_at = None

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.patch(
            f"/projects/{test_project_id}/exports/schedules/{schedule_id}",
            headers=auth_headers,
            json={"is_enabled": False},
        )

        data = response.json()
        assert data["is_enabled"] is False

    @pytest.mark.asyncio
    async def test_update_schedule_cron_expression(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that updating cron expression recalculates next_run_at."""
        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_schedule = MagicMock()
        mock_schedule.id = schedule_id
        mock_schedule.project_id = test_project_id
        mock_schedule.format = "csv"
        mock_schedule.resource = "issues"
        mock_schedule.cron_expression = "0 9 * * MON"
        mock_schedule.timezone = "UTC"
        mock_schedule.is_enabled = True
        mock_schedule.params = {}
        mock_schedule.last_run_at = None
        mock_schedule.next_run_at = datetime.now(UTC) + timedelta(days=1)
        mock_schedule.created_at = datetime.now(UTC)

        mock_schedule_result = MagicMock()
        mock_schedule_result.scalar_one_or_none.return_value = mock_schedule

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_schedule_result])
        mock_db_session.commit = AsyncMock()

        new_next_run = datetime.now(UTC) + timedelta(hours=12)

        async def mock_refresh(obj):
            obj.cron_expression = "0 0 * * *"
            obj.next_run_at = new_next_run

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = await client.patch(
            f"/projects/{test_project_id}/exports/schedules/{schedule_id}",
            headers=auth_headers,
            json={"cron_expression": "0 0 * * *"},
        )

        data = response.json()
        assert data["cron_expression"] == "0 0 * * *"
        assert data["next_run_at"] is not None

    @pytest.mark.asyncio
    async def test_update_schedule_invalid_cron_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that invalid cron expression in update returns 422."""
        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_schedule = MagicMock()
        mock_schedule.id = schedule_id
        mock_schedule.project_id = test_project_id
        mock_schedule.format = "csv"
        mock_schedule.resource = "issues"
        mock_schedule.cron_expression = "0 9 * * MON"
        mock_schedule.timezone = "UTC"
        mock_schedule.is_enabled = True
        mock_schedule.params = {}
        mock_schedule.last_run_at = None
        mock_schedule.next_run_at = datetime.now(UTC) + timedelta(days=1)
        mock_schedule.created_at = datetime.now(UTC)

        mock_schedule_result = MagicMock()
        mock_schedule_result.scalar_one_or_none.return_value = mock_schedule

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_schedule_result])

        response = await client.patch(
            f"/projects/{test_project_id}/exports/schedules/{schedule_id}",
            headers=auth_headers,
            json={"cron_expression": "not a valid cron"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_schedule_not_found_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that updating non-existent schedule returns 404."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_schedule_result = MagicMock()
        mock_schedule_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_schedule_result])

        random_schedule_id = uuid.uuid4()
        response = await client.patch(
            f"/projects/{test_project_id}/exports/schedules/{random_schedule_id}",
            headers=auth_headers,
            json={"is_enabled": False},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_schedule_requires_auth(
        self,
        client: AsyncClient,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that updating a schedule requires authentication."""
        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        response = await client.patch(
            f"/projects/{test_project_id}/exports/schedules/{schedule_id}",
            json={"is_enabled": False},
        )

        assert response.status_code == 401


class TestDeleteSchedule:
    """Tests for the DELETE /projects/{project_id}/exports/schedules/{schedule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_schedule_returns_204(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that deleting a schedule returns 204 No Content."""
        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_schedule = MagicMock()
        mock_schedule.id = schedule_id
        mock_schedule.project_id = test_project_id

        mock_schedule_result = MagicMock()
        mock_schedule_result.scalar_one_or_none.return_value = mock_schedule

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_schedule_result])
        mock_db_session.delete = AsyncMock()
        mock_db_session.commit = AsyncMock()

        response = await client.delete(
            f"/projects/{test_project_id}/exports/schedules/{schedule_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_schedule_not_found_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that deleting non-existent schedule returns 404."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_schedule_result = MagicMock()
        mock_schedule_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(side_effect=[mock_project_result, mock_schedule_result])

        random_schedule_id = uuid.uuid4()
        response = await client.delete(
            f"/projects/{test_project_id}/exports/schedules/{random_schedule_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_schedule_requires_auth(
        self,
        client: AsyncClient,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that deleting a schedule requires authentication."""
        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        response = await client.delete(
            f"/projects/{test_project_id}/exports/schedules/{schedule_id}",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_schedule_other_users_project_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        other_user_project: MagicMock,
    ) -> None:
        """Test that deleting a schedule for another user's project returns 404."""
        schedule_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.delete(
            f"/projects/{other_user_project.id}/exports/schedules/{schedule_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestScheduleCronValidation:
    """Tests for cron expression validation in schedule endpoints."""

    @pytest.mark.asyncio
    async def test_valid_cron_expressions(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that valid cron expressions are accepted."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        valid_crons = [
            "0 9 * * MON",  # Every Monday at 9:00
            "0 0 * * *",  # Every day at midnight
            "0 */6 * * *",  # Every 6 hours
            "0 9 1 * *",  # First day of month at 9:00
            "30 14 * * 1-5",  # Weekdays at 14:30
        ]

        for cron in valid_crons:

            def make_refresh(cron_expr: str):
                async def mock_refresh(obj):
                    obj.id = uuid.uuid4()
                    obj.project_id = test_project_id
                    obj.format = "csv"
                    obj.resource = "issues"
                    obj.cron_expression = cron_expr
                    obj.timezone = "UTC"
                    obj.is_enabled = True
                    obj.params = {}
                    obj.last_run_at = None
                    obj.next_run_at = datetime.now(UTC) + timedelta(days=1)
                    obj.created_at = datetime.now(UTC)

                return mock_refresh

            mock_db_session.refresh = AsyncMock(side_effect=make_refresh(cron))

            response = await client.post(
                f"/projects/{test_project_id}/exports/schedules",
                headers=auth_headers,
                json={
                    "format": "csv",
                    "resource": "issues",
                    "cron_expression": cron,
                },
            )

            assert response.status_code == 201, f"Failed for cron: {cron}"

    @pytest.mark.asyncio
    async def test_invalid_cron_expressions(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_db_session: AsyncMock,
        test_project: MagicMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that invalid cron expressions are rejected."""
        mock_project_result = MagicMock()
        mock_project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=mock_project_result)

        invalid_crons = [
            "not a cron",
            "* * * *",  # Missing field
            "60 * * * *",  # Invalid minute
            "* 24 * * *",  # Invalid hour
            "* * 32 * *",  # Invalid day of month
            "* * * 13 *",  # Invalid month
            "* * * * 8",  # Invalid day of week
            "",  # Empty string
        ]

        for cron in invalid_crons:
            response = await client.post(
                f"/projects/{test_project_id}/exports/schedules",
                headers=auth_headers,
                json={
                    "format": "csv",
                    "resource": "issues",
                    "cron_expression": cron,
                },
            )

            assert response.status_code == 422, f"Expected 422 for invalid cron: {cron}"
