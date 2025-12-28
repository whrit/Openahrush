"""
TDD tests for the diffs API endpoint.

Tests cover:
- GET /projects/{project_id}/issues/diffs endpoint
- Authentication requirements
- Validation of crawl run IDs
- Error handling
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


@pytest.fixture
def mock_crawl_run_a(test_project_id: uuid.UUID) -> MagicMock:
    """Create a mock crawl run A."""
    mock = MagicMock()
    mock.id = uuid.uuid4()
    mock.project_id = test_project_id
    mock.status = "completed"
    mock.created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    return mock


@pytest.fixture
def mock_crawl_run_b(test_project_id: uuid.UUID) -> MagicMock:
    """Create a mock crawl run B."""
    mock = MagicMock()
    mock.id = uuid.uuid4()
    mock.project_id = test_project_id
    mock.status = "completed"
    mock.created_at = datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC)
    return mock


@pytest.fixture
def mock_issues_a() -> list[MagicMock]:
    """Create mock issues for crawl A."""
    issues = []
    for i, (type_id, url, severity) in enumerate([
        ("missing_title", "https://example.com/page1", "critical"),
        ("missing_h1", "https://example.com/page2", "warning"),
    ]):
        mock = MagicMock()
        mock.id = uuid.uuid4()
        mock.issue_type_id = type_id
        mock.affected_url = url
        mock.severity = severity
        mock.confidence = Decimal("0.95")
        mock.message = f"Issue {i}"
        issues.append(mock)
    return issues


@pytest.fixture
def mock_issues_b() -> list[MagicMock]:
    """Create mock issues for crawl B (page1 fixed, page3 new)."""
    issues = []
    mock1 = MagicMock()
    mock1.id = uuid.uuid4()
    mock1.issue_type_id = "missing_h1"
    mock1.affected_url = "https://example.com/page2"
    mock1.severity = "warning"
    mock1.confidence = Decimal("0.95")
    mock1.message = "Issue 1"
    issues.append(mock1)

    mock2 = MagicMock()
    mock2.id = uuid.uuid4()
    mock2.issue_type_id = "broken_link"
    mock2.affected_url = "https://example.com/page3"
    mock2.severity = "critical"
    mock2.confidence = Decimal("0.90")
    mock2.message = "New issue"
    issues.append(mock2)

    return issues


class TestDiffsEndpoint:
    """Tests for GET /projects/{project_id}/issues/diffs."""

    @pytest.mark.asyncio
    async def test_requires_authentication(
        self,
        client: AsyncClient,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test that endpoint requires authentication."""
        from_crawl = uuid.uuid4()
        to_crawl = uuid.uuid4()

        response = await client.get(
            f"/projects/{test_project_id}/issues/diffs",
            params={"from_crawl_run_id": str(from_crawl), "to_crawl_run_id": str(to_crawl)},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_400_for_different_projects(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_db_session: AsyncMock,
        test_project_id: uuid.UUID,
        test_user_id: uuid.UUID,
    ) -> None:
        """Test that 400 is returned if crawl runs are from different projects."""
        # Create crawl runs from different projects
        crawl_a = MagicMock()
        crawl_a.id = uuid.uuid4()
        crawl_a.project_id = test_project_id

        crawl_b = MagicMock()
        crawl_b.id = uuid.uuid4()
        crawl_b.project_id = uuid.uuid4()  # Different project

        # Mock project lookup (project exists and user owns it)
        mock_project = MagicMock()
        mock_project.id = test_project_id
        mock_project.owner_id = test_user_id

        mock_result_project = MagicMock()
        mock_result_project.scalar_one_or_none.return_value = mock_project

        mock_result_crawl_a = MagicMock()
        mock_result_crawl_a.scalar_one_or_none.return_value = crawl_a

        mock_result_crawl_b = MagicMock()
        mock_result_crawl_b.scalar_one_or_none.return_value = crawl_b

        # Return different results for different queries
        mock_db_session.execute.side_effect = [
            mock_result_project,  # project lookup
            mock_result_crawl_a,  # crawl A lookup
            mock_result_crawl_b,  # crawl B lookup
        ]

        response = await client.get(
            f"/projects/{test_project_id}/issues/diffs",
            params={"from_crawl_run_id": str(crawl_a.id), "to_crawl_run_id": str(crawl_b.id)},
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "same project" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_crawl_run(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_db_session: AsyncMock,
        test_project_id: uuid.UUID,
        test_user_id: uuid.UUID,
    ) -> None:
        """Test that 404 is returned if crawl run doesn't exist."""
        from_crawl = uuid.uuid4()
        to_crawl = uuid.uuid4()

        # Mock project lookup (project exists and user owns it)
        mock_project = MagicMock()
        mock_project.id = test_project_id
        mock_project.owner_id = test_user_id

        mock_result_project = MagicMock()
        mock_result_project.scalar_one_or_none.return_value = mock_project

        # Mock crawl run lookup - not found
        mock_result_crawl = MagicMock()
        mock_result_crawl.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [
            mock_result_project,  # project lookup
            mock_result_crawl,  # crawl A lookup - not found
        ]

        response = await client.get(
            f"/projects/{test_project_id}/issues/diffs",
            params={"from_crawl_run_id": str(from_crawl), "to_crawl_run_id": str(to_crawl)},
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_diff_result(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_db_session: AsyncMock,
        test_project_id: uuid.UUID,
        test_user_id: uuid.UUID,
        mock_crawl_run_a: MagicMock,
        mock_crawl_run_b: MagicMock,
        mock_issues_a: list[MagicMock],
        mock_issues_b: list[MagicMock],
    ) -> None:
        """Test that diff result is returned correctly."""
        # Mock project lookup
        mock_project = MagicMock()
        mock_project.id = test_project_id
        mock_project.owner_id = test_user_id

        mock_result_project = MagicMock()
        mock_result_project.scalar_one_or_none.return_value = mock_project

        # Mock crawl run lookups
        mock_result_crawl_a = MagicMock()
        mock_result_crawl_a.scalar_one_or_none.return_value = mock_crawl_run_a

        mock_result_crawl_b = MagicMock()
        mock_result_crawl_b.scalar_one_or_none.return_value = mock_crawl_run_b

        # Mock issue lookups
        mock_result_issues_a = MagicMock()
        mock_result_issues_a.scalars.return_value.all.return_value = mock_issues_a

        mock_result_issues_b = MagicMock()
        mock_result_issues_b.scalars.return_value.all.return_value = mock_issues_b

        mock_db_session.execute.side_effect = [
            mock_result_project,  # project lookup
            mock_result_crawl_a,  # crawl A lookup
            mock_result_crawl_b,  # crawl B lookup
            mock_result_issues_a,  # issues A lookup
            mock_result_issues_b,  # issues B lookup
        ]

        response = await client.get(
            f"/projects/{test_project_id}/issues/diffs",
            params={
                "from_crawl_run_id": str(mock_crawl_run_a.id),
                "to_crawl_run_id": str(mock_crawl_run_b.id),
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should have 1 added (broken_link), 1 resolved (missing_title), 0 changed
        assert "added" in data
        assert "resolved" in data
        assert "changed" in data
        assert "summary" in data

        assert len(data["added"]) == 1
        assert data["added"][0]["issue_type_id"] == "broken_link"

        assert len(data["resolved"]) == 1
        assert data["resolved"][0]["issue_type_id"] == "missing_title"

        assert len(data["changed"]) == 0

    @pytest.mark.asyncio
    async def test_project_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that 404 is returned if project doesn't exist."""
        project_id = uuid.uuid4()
        from_crawl = uuid.uuid4()
        to_crawl = uuid.uuid4()

        # Mock project lookup - not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = await client.get(
            f"/projects/{project_id}/issues/diffs",
            params={"from_crawl_run_id": str(from_crawl), "to_crawl_run_id": str(to_crawl)},
            headers=auth_headers,
        )

        assert response.status_code == 404
