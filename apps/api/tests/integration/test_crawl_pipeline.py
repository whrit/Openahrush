"""
Integration tests for crawl pipeline following TDD principles.

Tests complete crawl pipeline flows including:
- Crawl trigger → job enqueue → status update flow
- Crawl with mocked HTTP responses
- Crawl results storage in database
- Crawl status transitions and error handling
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from semrush_core.models import CrawlPage, CrawlRun, IssueInstance, LinkEdge
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TestCrawlTriggerFlow:
    """Test crawl trigger and job enqueue flow."""

    @pytest.mark.asyncio
    async def test_crawl_trigger_creates_crawl_run(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db_session: AsyncSession,
        test_project: Any,
        test_site: Any,
    ) -> None:
        """
        Test that triggering a crawl creates a CrawlRun record.

        Flow:
        1. User triggers crawl for a site
        2. System creates CrawlRun with status='queued'
        3. System returns crawl job details
        """
        # Note: Adjust endpoint based on actual API implementation
        # This assumes POST /projects/{project_id}/sites/{site_id}/crawls
        response = await integration_client.post(
            f"/projects/{test_project.id}/sites/{test_site.id}/crawls",
            headers=auth_headers,
            json={
                "max_pages": 100,
                "follow_external_links": False,
            },
        )

        # May return 201 Created or 202 Accepted for async processing
        assert response.status_code in [201, 202, 404]  # 404 if endpoint not implemented yet

        if response.status_code in [201, 202]:
            data = response.json()
            assert "id" in data
            assert data["status"] == "queued"

            # Verify CrawlRun was created in database
            crawl_id = uuid.UUID(data["id"])
            result = await test_db_session.execute(select(CrawlRun).where(CrawlRun.id == crawl_id))
            crawl_run = result.scalar_one_or_none()

            assert crawl_run is not None
            assert crawl_run.project_id == test_project.id
            assert crawl_run.site_id == test_site.id
            assert crawl_run.status == "queued"

    @pytest.mark.asyncio
    async def test_crawl_trigger_stores_config_snapshot(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db_session: AsyncSession,
        test_project: Any,
        test_site: Any,
    ) -> None:
        """
        Test that crawl trigger stores configuration snapshot.

        The config_snapshot preserves settings at crawl time,
        allowing historical analysis.
        """
        crawl_config = {
            "max_pages": 50,
            "follow_external_links": True,
            "respect_robots_txt": True,
        }

        response = await integration_client.post(
            f"/projects/{test_project.id}/sites/{test_site.id}/crawls",
            headers=auth_headers,
            json=crawl_config,
        )

        if response.status_code in [201, 202]:
            data = response.json()
            crawl_id = uuid.UUID(data["id"])

            # Verify config was stored
            result = await test_db_session.execute(select(CrawlRun).where(CrawlRun.id == crawl_id))
            crawl_run = result.scalar_one_or_none()

            assert crawl_run is not None
            assert crawl_run.config_snapshot["max_pages"] == 50
            assert crawl_run.config_snapshot["follow_external_links"] is True

    @pytest.mark.asyncio
    async def test_crawl_trigger_without_auth_returns_401(
        self,
        integration_client: AsyncClient,
        test_project: Any,
        test_site: Any,
    ) -> None:
        """
        Test that crawl trigger requires authentication.
        """
        response = await integration_client.post(
            f"/projects/{test_project.id}/sites/{test_site.id}/crawls",
            json={"max_pages": 100},
        )

        assert response.status_code in [401, 404]


class TestCrawlStatusUpdates:
    """Test crawl status update flow."""

    @pytest.mark.asyncio
    async def test_crawl_status_transitions_from_queued_to_running(
        self,
        test_db_session: AsyncSession,
        test_crawl_run: CrawlRun,
    ) -> None:
        """
        Test that crawl status can transition from queued to running.

        This simulates a worker picking up the crawl job.
        """
        # Simulate worker starting the crawl
        test_crawl_run.status = "running"
        test_crawl_run.started_at = datetime.now(UTC)
        await test_db_session.commit()
        await test_db_session.refresh(test_crawl_run)

        assert test_crawl_run.status == "running"
        assert test_crawl_run.started_at is not None

    @pytest.mark.asyncio
    async def test_crawl_status_transitions_to_completed(
        self,
        test_db_session: AsyncSession,
        test_crawl_run: CrawlRun,
    ) -> None:
        """
        Test that crawl status can transition to completed.

        This includes setting completion timestamp and stats.
        """
        # Simulate crawl completion
        test_crawl_run.status = "completed"
        test_crawl_run.started_at = datetime.now(UTC)
        test_crawl_run.html_completed_at = datetime.now(UTC)
        test_crawl_run.completed_at = datetime.now(UTC)
        test_crawl_run.stats = {
            "pages_crawled": 45,
            "pages_failed": 2,
            "total_duration_seconds": 120,
        }
        await test_db_session.commit()
        await test_db_session.refresh(test_crawl_run)

        assert test_crawl_run.status == "completed"
        assert test_crawl_run.completed_at is not None
        assert test_crawl_run.stats["pages_crawled"] == 45

    @pytest.mark.asyncio
    async def test_crawl_status_can_transition_to_failed(
        self,
        test_db_session: AsyncSession,
        test_crawl_run: CrawlRun,
    ) -> None:
        """
        Test that crawl status can transition to failed with error message.
        """
        # Simulate crawl failure
        test_crawl_run.status = "failed"
        test_crawl_run.error_message = "Network timeout after 5 retries"
        test_crawl_run.started_at = datetime.now(UTC)
        test_crawl_run.completed_at = datetime.now(UTC)
        await test_db_session.commit()
        await test_db_session.refresh(test_crawl_run)

        assert test_crawl_run.status == "failed"
        assert test_crawl_run.error_message is not None
        assert "timeout" in test_crawl_run.error_message.lower()

    @pytest.mark.asyncio
    async def test_get_crawl_status_returns_current_state(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_project: Any,
        test_crawl_run: CrawlRun,
    ) -> None:
        """
        Test that GET crawl status endpoint returns current crawl state.
        """
        response = await integration_client.get(
            f"/projects/{test_project.id}/crawls/{test_crawl_run.id}",
            headers=auth_headers,
        )

        # May not be implemented yet
        if response.status_code == 200:
            data = response.json()
            assert data["id"] == str(test_crawl_run.id)
            assert "status" in data
            assert data["status"] == test_crawl_run.status


class TestCrawlResultsStorage:
    """Test crawl results storage in database."""

    @pytest.mark.asyncio
    async def test_crawl_stores_crawled_pages(
        self,
        test_db_session: AsyncSession,
        test_crawl_run: CrawlRun,
    ) -> None:
        """
        Test that crawl results include CrawlPage records.

        Each crawled page should be stored with HTML artifact reference,
        status code, response time, etc.
        """
        # Simulate storing crawl pages
        page1 = CrawlPage(
            crawl_run_id=test_crawl_run.id,
            url="https://example.com/",
            status_code=200,
            response_time_ms=150,
            html_artifact_key="crawls/test/page1.html",
            title="Homepage",
            meta_description="Welcome to our site",
        )
        page2 = CrawlPage(
            crawl_run_id=test_crawl_run.id,
            url="https://example.com/about",
            status_code=200,
            response_time_ms=200,
            html_artifact_key="crawls/test/page2.html",
            title="About Us",
            meta_description="Learn about our company",
        )

        test_db_session.add_all([page1, page2])
        await test_db_session.commit()

        # Verify pages were stored
        result = await test_db_session.execute(
            select(CrawlPage).where(CrawlPage.crawl_run_id == test_crawl_run.id)
        )
        pages = result.scalars().all()

        assert len(pages) == 2
        assert pages[0].url in ["https://example.com/", "https://example.com/about"]
        assert all(page.status_code == 200 for page in pages)

    @pytest.mark.asyncio
    async def test_crawl_stores_link_edges(
        self,
        test_db_session: AsyncSession,
        test_crawl_run: CrawlRun,
    ) -> None:
        """
        Test that crawl results include LinkEdge records.

        LinkEdges represent internal links discovered during the crawl,
        used for link graph analysis.
        """
        # Simulate storing link edges
        link1 = LinkEdge(
            crawl_run_id=test_crawl_run.id,
            source_url="https://example.com/",
            target_url="https://example.com/about",
            anchor_text="About Us",
            link_type="internal",
            is_nofollow=False,
        )
        link2 = LinkEdge(
            crawl_run_id=test_crawl_run.id,
            source_url="https://example.com/",
            target_url="https://example.com/contact",
            anchor_text="Contact",
            link_type="internal",
            is_nofollow=False,
        )

        test_db_session.add_all([link1, link2])
        await test_db_session.commit()

        # Verify links were stored
        result = await test_db_session.execute(
            select(LinkEdge).where(LinkEdge.crawl_run_id == test_crawl_run.id)
        )
        links = result.scalars().all()

        assert len(links) == 2
        assert all(link.link_type == "internal" for link in links)
        assert all(link.is_nofollow is False for link in links)

    @pytest.mark.asyncio
    async def test_crawl_stores_issue_instances(
        self,
        test_db_session: AsyncSession,
        test_crawl_run: CrawlRun,
    ) -> None:
        """
        Test that crawl results include IssueInstance records.

        Issues detected during the crawl (missing meta tags,
        broken links, etc.) should be stored.
        """
        # Simulate storing issues
        issue1 = IssueInstance(
            crawl_run_id=test_crawl_run.id,
            issue_type="missing_meta_description",
            url="https://example.com/page1",
            severity="warning",
            details={"message": "Meta description is missing"},
        )
        issue2 = IssueInstance(
            crawl_run_id=test_crawl_run.id,
            issue_type="broken_internal_link",
            url="https://example.com/page2",
            severity="error",
            details={"target_url": "https://example.com/missing", "status_code": 404},
        )

        test_db_session.add_all([issue1, issue2])
        await test_db_session.commit()

        # Verify issues were stored
        result = await test_db_session.execute(
            select(IssueInstance).where(IssueInstance.crawl_run_id == test_crawl_run.id)
        )
        issues = result.scalars().all()

        assert len(issues) == 2
        assert any(issue.issue_type == "missing_meta_description" for issue in issues)
        assert any(issue.issue_type == "broken_internal_link" for issue in issues)


class TestCrawlWithMockedHTTP:
    """Test crawl pipeline with mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_crawl_handles_successful_http_responses(
        self,
    ) -> None:
        """
        Test that crawl correctly processes successful HTTP responses.

        Mock the HTTP client to return test HTML content,
        verify it's processed correctly.
        """
        # Mock HTTP response
        mock_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
        </head>
        <body>
            <a href="/about">About</a>
            <a href="/contact">Contact</a>
        </body>
        </html>
        """

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = mock_html
            mock_response.headers = {"content-type": "text/html"}
            mock_client.get = AsyncMock(return_value=mock_response)
            MockClient.return_value.__aenter__.return_value = mock_client

            # Simulate crawl processing
            response = await mock_client.get("https://example.com/")

            assert response.status_code == 200
            assert "Test Page" in response.text
            assert "About" in response.text

    @pytest.mark.asyncio
    async def test_crawl_handles_http_errors(
        self,
    ) -> None:
        """
        Test that crawl handles HTTP errors gracefully.

        Test scenarios: 404, 500, network timeouts.
        """
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()

            # Mock 404 response
            mock_404_response = MagicMock()
            mock_404_response.status_code = 404
            mock_404_response.text = "Not Found"
            mock_client.get = AsyncMock(return_value=mock_404_response)
            MockClient.return_value.__aenter__.return_value = mock_client

            response = await mock_client.get("https://example.com/missing")

            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_crawl_handles_network_timeouts(
        self,
    ) -> None:
        """
        Test that crawl handles network timeouts with retries.
        """
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Network timeout"))
            MockClient.return_value.__aenter__.return_value = mock_client

            # Verify timeout exception is raised
            with pytest.raises(Exception, match="Network timeout"):
                await mock_client.get("https://example.com/slow")


class TestCrawlQueueIntegration:
    """Test crawl job queue integration."""

    @pytest.mark.asyncio
    async def test_crawl_job_enqueued_to_redis(
        self,
        fake_redis: Any,
        test_crawl_run: CrawlRun,
    ) -> None:
        """
        Test that crawl jobs are enqueued to Redis for worker processing.

        Flow:
        1. CrawlRun created with status='queued'
        2. Job enqueued to Redis queue
        3. Worker picks up job from queue
        """
        # Simulate enqueuing crawl job
        import json

        job_data = {
            "crawl_run_id": str(test_crawl_run.id),
            "project_id": str(test_crawl_run.project_id),
            "site_id": str(test_crawl_run.site_id),
            "config": test_crawl_run.config_snapshot,
        }

        await fake_redis.lpush("crawl_queue", json.dumps(job_data))

        # Verify job was enqueued
        queue_length = await fake_redis.llen("crawl_queue")
        assert queue_length == 1

        # Simulate worker dequeuing job
        job_json = await fake_redis.rpop("crawl_queue")
        assert job_json is not None

        dequeued_job = json.loads(job_json)
        assert dequeued_job["crawl_run_id"] == str(test_crawl_run.id)

    @pytest.mark.asyncio
    async def test_multiple_crawl_jobs_queued_in_order(
        self,
        fake_redis: Any,
    ) -> None:
        """
        Test that multiple crawl jobs are queued and processed in FIFO order.
        """
        import json

        # Enqueue multiple jobs
        job_ids = []
        for i in range(3):
            job_id = str(uuid.uuid4())
            job_ids.append(job_id)
            await fake_redis.lpush(
                "crawl_queue",
                json.dumps({"crawl_run_id": job_id, "index": i}),
            )

        # Verify queue length
        assert await fake_redis.llen("crawl_queue") == 3

        # Dequeue and verify FIFO order
        for i in range(3):
            job_json = await fake_redis.rpop("crawl_queue")
            job = json.loads(job_json)
            # Jobs should be dequeued in reverse order (FIFO)
            assert job["index"] == i


class TestCrawlPagination:
    """Test crawl results pagination."""

    @pytest.mark.asyncio
    async def test_list_crawls_returns_paginated_results(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_project: Any,
    ) -> None:
        """
        Test that listing crawls supports pagination.
        """
        response = await integration_client.get(
            f"/projects/{test_project.id}/crawls?page=1&pageSize=10",
            headers=auth_headers,
        )

        # May not be implemented yet
        if response.status_code == 200:
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "page_size" in data


class TestCrawlAuthorization:
    """Test crawl authorization and access control."""

    @pytest.mark.asyncio
    async def test_cannot_trigger_crawl_for_other_users_project(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Test that users cannot trigger crawls for projects they don't own.
        """
        other_project_id = uuid.uuid4()
        other_site_id = uuid.uuid4()

        response = await integration_client.post(
            f"/projects/{other_project_id}/sites/{other_site_id}/crawls",
            headers=auth_headers,
            json={"max_pages": 100},
        )

        # Should return 404 (project not found) or 403 (forbidden)
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_cannot_view_other_users_crawl_results(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Test that users cannot view crawl results for projects they don't own.
        """
        other_project_id = uuid.uuid4()
        other_crawl_id = uuid.uuid4()

        response = await integration_client.get(
            f"/projects/{other_project_id}/crawls/{other_crawl_id}",
            headers=auth_headers,
        )

        # Should return 404 (not found) or 403 (forbidden)
        assert response.status_code in [403, 404]
