"""
Pytest fixtures for reports testing.

Provides:
- Mock database sessions
- Test data fixtures
- Storage mocks
"""

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# Set test environment variables before importing app
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-at-least-32-characters-long")
os.environ.setdefault("ENVIRONMENT", "development")


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Configure anyio to use asyncio backend."""
    return "asyncio"


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """
    Create a mock database session for isolated testing.

    Returns:
        AsyncMock configured as a database session.
    """
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def test_project_id() -> uuid.UUID:
    """Generate a consistent test project ID."""
    return uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def test_crawl_run_id() -> uuid.UUID:
    """Generate a consistent test crawl run ID."""
    return uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def test_export_id() -> uuid.UUID:
    """Generate a consistent test export ID."""
    return uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture
def mock_project(test_project_id: uuid.UUID) -> MagicMock:
    """Create a mock project."""
    project = MagicMock()
    project.id = test_project_id
    project.name = "Test Project"
    project.created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    project.updated_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    return project


@pytest.fixture
def mock_crawl_run(test_crawl_run_id: uuid.UUID, test_project_id: uuid.UUID) -> MagicMock:
    """Create a mock crawl run."""
    crawl_run = MagicMock()
    crawl_run.id = test_crawl_run_id
    crawl_run.project_id = test_project_id
    crawl_run.status = "completed"
    crawl_run.created_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    return crawl_run


@pytest.fixture
def mock_issues(test_crawl_run_id: uuid.UUID) -> list[MagicMock]:
    """Create mock issue instances."""
    issues = []
    for i in range(5):
        issue = MagicMock()
        issue.id = uuid.uuid4()
        issue.crawl_run_id = test_crawl_run_id
        issue.crawl_page_id = uuid.uuid4()
        issue.affected_url = f"https://example.com/page-{i}"
        issue.confidence = Decimal("0.95")
        issue.impact_score = Decimal("75.50")
        issue.evidence = {"detail": f"Issue {i}"}

        # Mock issue type
        issue_type = MagicMock()
        issue_type.id = f"issue_type_{i}"
        issue_type.category = "content" if i % 2 == 0 else "performance"
        issue_type.severity = 5 - i  # Varying severity
        issue_type.description = f"Test issue type {i}"
        issue.issue_type = issue_type

        issues.append(issue)
    return issues


@pytest.fixture
def mock_backlinks(test_project_id: uuid.UUID) -> list[MagicMock]:
    """Create mock backlinks."""
    backlinks = []
    for i in range(5):
        bl = MagicMock()
        bl.id = uuid.uuid4()
        bl.project_id = test_project_id
        bl.source_url = f"https://source{i}.com/page"
        bl.source_domain = f"source{i}.com"
        bl.target_url = "https://example.com/target"
        bl.target_domain = "example.com"
        bl.anchor = f"Anchor text {i}"
        bl.rel_flags = ["nofollow"] if i % 2 == 0 else None
        bl.source_type = "commoncrawl"
        bl.discovered_at = datetime(2024, 1, 10 + i, 0, 0, 0, tzinfo=UTC)

        # Properties
        bl.is_dofollow = i % 2 != 0
        bl.is_nofollow = i % 2 == 0
        bl.is_ugc = False
        bl.is_sponsored = False

        backlinks.append(bl)
    return backlinks


@pytest.fixture
def mock_crawl_pages(test_crawl_run_id: uuid.UUID) -> list[MagicMock]:
    """Create mock crawl pages."""
    pages = []
    for i in range(5):
        page = MagicMock()
        page.id = uuid.uuid4()
        page.crawl_run_id = test_crawl_run_id
        page.url = f"https://example.com/page-{i}"
        page.final_url = f"https://example.com/page-{i}"
        page.status_code = 200 if i < 4 else 404
        page.content_type = "text/html"
        page.response_time_ms = 100 + i * 50
        page.title = f"Page {i} Title"
        page.meta_description = f"Description for page {i}"
        page.canonical_url = f"https://example.com/page-{i}"
        page.h1_count = 1
        page.first_h1 = f"Heading {i}"
        page.word_count = 500 + i * 100
        page.render_mode = "html"
        page.was_rendered = False
        pages.append(page)
    return pages


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create a mock MinIO storage."""
    storage = MagicMock()
    storage.upload = MagicMock(return_value="s3://bucket/key")
    storage.presigned_url = MagicMock(return_value="https://presigned.url/key")
    storage.delete = MagicMock()
    storage.exists = MagicMock(return_value=True)
    storage.get_size = MagicMock(return_value=1024)
    return storage
