"""
Tests for the issues router.

Tests cover:
- GET /crawls/{crawl_run_id}/issues - List issues for a crawl
- GET /projects/{project_id}/issues - Get issues from latest crawl
- Pagination, sorting, and filtering
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def test_crawl_run_id() -> uuid.UUID:
    """Test crawl run ID."""
    return uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def sample_issue_type() -> MagicMock:
    """Create a sample issue type."""
    issue_type = MagicMock()
    issue_type.id = "missing_title"
    issue_type.category = "content"
    issue_type.severity = 4
    issue_type.name = "Missing Title"
    issue_type.description = "Page is missing a title tag"
    issue_type.recommendation = "Add a descriptive title tag"
    return issue_type


@pytest.fixture
def sample_issues(
    test_crawl_run_id: uuid.UUID, sample_issue_type: MagicMock
) -> list[MagicMock]:
    """Create sample issue instances."""
    issues = []

    # Create mock crawl run for both issues
    mock_crawl_run = MagicMock()
    mock_crawl_run.id = test_crawl_run_id
    mock_crawl_run.created_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)

    issue1 = MagicMock()
    issue1.id = uuid.uuid4()
    issue1.crawl_run_id = test_crawl_run_id
    issue1.crawl_page_id = uuid.uuid4()
    issue1.issue_type_id = "missing_title"
    issue1.affected_url = "https://example.com/page1"
    issue1.confidence = 1.0
    issue1.impact_score = 4.0
    issue1.evidence = {"expected": "non-empty title", "found": None}
    issue1.issue_type = sample_issue_type
    issue1.crawl_run = mock_crawl_run
    issues.append(issue1)

    thin_type = MagicMock()
    thin_type.id = "thin_content"
    thin_type.category = "content"
    thin_type.severity = 2
    thin_type.name = "Thin Content"
    thin_type.description = "Page has thin content"
    thin_type.recommendation = "Add more content"

    issue2 = MagicMock()
    issue2.id = uuid.uuid4()
    issue2.crawl_run_id = test_crawl_run_id
    issue2.crawl_page_id = uuid.uuid4()
    issue2.issue_type_id = "thin_content"
    issue2.affected_url = "https://example.com/page2"
    issue2.confidence = 0.75
    issue2.impact_score = 1.5
    issue2.evidence = {"word_count": 50, "min_words": 300}
    issue2.issue_type = thin_type
    issue2.crawl_run = mock_crawl_run
    issues.append(issue2)

    return issues


@pytest.fixture
def mock_crawl_run(
    test_crawl_run_id: uuid.UUID, test_project_id: uuid.UUID
) -> MagicMock:
    """Create a mock crawl run."""
    crawl = MagicMock()
    crawl.id = test_crawl_run_id
    crawl.project_id = test_project_id
    crawl.status = "completed"
    crawl.created_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    return crawl


class TestGetCrawlIssues:
    """Tests for GET /crawls/{crawl_run_id}/issues."""

    @pytest.mark.asyncio
    async def test_list_issues_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_crawl_run_id,
        test_project_id,
        test_user_id,
        sample_issues,
        test_project,
        mock_crawl_run,
    ):
        """Successfully list issues for a crawl."""
        # Mock crawl run lookup
        crawl_result = MagicMock()
        crawl_result.scalar_one_or_none.return_value = mock_crawl_run

        # Mock project ownership lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Mock issues count
        count_result = MagicMock()
        count_result.scalar.return_value = len(sample_issues)

        # Mock issues list
        issues_result = MagicMock()
        issues_result.scalars.return_value.all.return_value = sample_issues

        mock_db_session.execute = AsyncMock(
            side_effect=[
                crawl_result,
                project_result,
                count_result,
                issues_result,
            ]
        )

        response = await client.get(
            f"/crawls/{test_crawl_run_id}/issues",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == len(sample_issues)

    @pytest.mark.asyncio
    async def test_list_issues_with_pagination(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_crawl_run_id,
        sample_issues,
        test_project,
        mock_crawl_run,
    ):
        """Pagination parameters are applied."""
        crawl_result = MagicMock()
        crawl_result.scalar_one_or_none.return_value = mock_crawl_run

        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        count_result = MagicMock()
        count_result.scalar.return_value = 50

        issues_result = MagicMock()
        issues_result.scalars.return_value.all.return_value = sample_issues[:1]

        mock_db_session.execute = AsyncMock(
            side_effect=[
                crawl_result,
                project_result,
                count_result,
                issues_result,
            ]
        )

        response = await client.get(
            f"/crawls/{test_crawl_run_id}/issues?page=2&pageSize=10",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert data["total"] == 50

    @pytest.mark.asyncio
    async def test_list_issues_with_sort(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_crawl_run_id,
        sample_issues,
        test_project,
        mock_crawl_run,
    ):
        """Sort parameters are applied."""
        crawl_result = MagicMock()
        crawl_result.scalar_one_or_none.return_value = mock_crawl_run

        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        count_result = MagicMock()
        count_result.scalar.return_value = 2

        issues_result = MagicMock()
        issues_result.scalars.return_value.all.return_value = sample_issues

        mock_db_session.execute = AsyncMock(
            side_effect=[
                crawl_result,
                project_result,
                count_result,
                issues_result,
            ]
        )

        response = await client.get(
            f"/crawls/{test_crawl_run_id}/issues?sortBy=severity&sortOrder=asc",
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_issues_with_filter(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_crawl_run_id,
        sample_issues,
        test_project,
        mock_crawl_run,
    ):
        """Filter parameters are applied."""
        crawl_result = MagicMock()
        crawl_result.scalar_one_or_none.return_value = mock_crawl_run

        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        count_result = MagicMock()
        count_result.scalar.return_value = 1

        issues_result = MagicMock()
        issues_result.scalars.return_value.all.return_value = [sample_issues[0]]

        mock_db_session.execute = AsyncMock(
            side_effect=[
                crawl_result,
                project_result,
                count_result,
                issues_result,
            ]
        )

        response = await client.get(
            f"/crawls/{test_crawl_run_id}/issues?issueTypeId=missing_title&severity=4",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_issues_crawl_not_found(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 404 for non-existent crawl run."""
        crawl_result = MagicMock()
        crawl_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=crawl_result)

        response = await client.get(
            f"/crawls/{uuid.uuid4()}/issues",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_issues_unauthorized(
        self,
        client,
        test_crawl_run_id,
    ):
        """Returns 401 without authentication."""
        response = await client.get(f"/crawls/{test_crawl_run_id}/issues")

        assert response.status_code == 401


class TestGetProjectIssues:
    """Tests for GET /projects/{project_id}/issues."""

    @pytest.mark.asyncio
    async def test_get_latest_issues_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        sample_issues,
        test_project,
        mock_crawl_run,
    ):
        """Successfully get issues from latest crawl."""
        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Mock latest crawl lookup
        crawl_result = MagicMock()
        crawl_result.scalar_one_or_none.return_value = mock_crawl_run

        # Mock issues
        issues_result = MagicMock()
        issues_result.scalars.return_value.all.return_value = sample_issues

        mock_db_session.execute = AsyncMock(
            side_effect=[
                project_result,
                crawl_result,
                issues_result,
            ]
        )

        response = await client.get(
            f"/projects/{test_project_id}/issues",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == len(sample_issues)

    @pytest.mark.asyncio
    async def test_get_latest_issues_with_limit(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        sample_issues,
        test_project,
        mock_crawl_run,
    ):
        """Limit parameter is applied."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        crawl_result = MagicMock()
        crawl_result.scalar_one_or_none.return_value = mock_crawl_run

        issues_result = MagicMock()
        issues_result.scalars.return_value.all.return_value = sample_issues[:1]

        mock_db_session.execute = AsyncMock(
            side_effect=[
                project_result,
                crawl_result,
                issues_result,
            ]
        )

        response = await client.get(
            f"/projects/{test_project_id}/issues?limit=1",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_get_latest_issues_no_crawls(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Returns 404 when no crawl runs exist."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        crawl_result = MagicMock()
        crawl_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(
            side_effect=[project_result, crawl_result]
        )

        response = await client.get(
            f"/projects/{test_project_id}/issues",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_latest_issues_project_not_found(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 404 for non-existent project."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=project_result)

        response = await client.get(
            f"/projects/{uuid.uuid4()}/issues",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_latest_issues_sorted_by_impact(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        sample_issues,
        test_project,
        mock_crawl_run,
    ):
        """Issues are sorted by impact_score DESC by default."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        crawl_result = MagicMock()
        crawl_result.scalar_one_or_none.return_value = mock_crawl_run

        # Return issues in correct order (highest impact first)
        sorted_issues = sorted(
            sample_issues,
            key=lambda x: x.impact_score or 0,
            reverse=True,
        )
        issues_result = MagicMock()
        issues_result.scalars.return_value.all.return_value = sorted_issues

        mock_db_session.execute = AsyncMock(
            side_effect=[
                project_result,
                crawl_result,
                issues_result,
            ]
        )

        response = await client.get(
            f"/projects/{test_project_id}/issues",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        items = data["items"]
        if len(items) > 1:
            # First item should have highest impact score
            assert items[0]["impact_score"] >= items[1]["impact_score"]

    @pytest.mark.asyncio
    async def test_get_latest_issues_requires_auth(
        self,
        client,
        test_project_id,
    ):
        """Returns 401 without authentication."""
        response = await client.get(f"/projects/{test_project_id}/issues")
        assert response.status_code == 401
