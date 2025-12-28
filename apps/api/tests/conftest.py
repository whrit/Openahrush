"""
Pytest fixtures for API testing.

Provides:
- Async test client configuration
- Database test fixtures with transaction rollback
- Test user creation and authentication fixtures
- Mock dependencies for isolated testing
"""

import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Set test environment variables before importing app
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-at-least-32-characters-long")
os.environ.setdefault("ENVIRONMENT", "development")

from datetime import UTC

from semrush_core.config import Settings, get_settings
from semrush_core.database import get_async_session
from semrush_core.security.jwt import create_access_token
from semrush_core.security.password import hash_password


def get_test_settings() -> Settings:
    """
    Get test settings that override production settings.

    Returns:
        Settings configured for testing.
    """
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
        redis_url="redis://localhost:6379/0",
        jwt_secret="test-secret-key-that-is-at-least-32-characters-long",  # type: ignore[arg-type]
        environment="development",
        debug=True,
    )


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Configure anyio to use asyncio backend."""
    return "asyncio"


@pytest.fixture
def mock_settings() -> Settings:
    """
    Fixture providing test settings.

    Returns:
        Test settings instance.
    """
    return get_test_settings()


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


@pytest_asyncio.fixture
async def client(mock_db_session: AsyncMock, mock_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async HTTP client for testing the API.

    Uses mocked database session and settings to ensure tests
    are isolated and do not require actual infrastructure.

    Args:
        mock_db_session: Mocked database session.
        mock_settings: Test settings.

    Yields:
        Configured async HTTP client.
    """
    from semrush_api.main import create_app

    app = create_app()

    # Override dependencies
    async def override_get_async_session():
        yield mock_db_session

    def override_get_settings():
        return mock_settings

    app.dependency_overrides[get_async_session] = override_get_async_session
    app.dependency_overrides[get_settings] = override_get_settings

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def test_user_id() -> uuid.UUID:
    """
    Generate a consistent test user ID.

    Returns:
        UUID for test user.
    """
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def test_user_email() -> str:
    """
    Test user email address.

    Returns:
        Email string for test user.
    """
    return "test@example.com"


@pytest.fixture
def test_user_password() -> str:
    """
    Test user password (plain text).

    Returns:
        Plain text password for test user.
    """
    return "testpassword123"


@pytest.fixture
def test_user_password_hash(test_user_password: str) -> str:
    """
    Test user password hash.

    Args:
        test_user_password: Plain text password.

    Returns:
        Bcrypt hash of the password.
    """
    return hash_password(test_user_password)


@pytest.fixture
def test_user_data(
    test_user_id: uuid.UUID,
    test_user_email: str,
    test_user_password_hash: str,
) -> dict[str, Any]:
    """
    Complete test user data.

    Args:
        test_user_id: User UUID.
        test_user_email: User email.
        test_user_password_hash: Hashed password.

    Returns:
        Dictionary with all user fields.
    """
    return {
        "id": test_user_id,
        "email": test_user_email,
        "password_hash": test_user_password_hash,
        "name": "Test User",
        "is_active": True,
    }


@pytest.fixture
def auth_token(test_user_id: uuid.UUID) -> str:
    """
    Generate a valid JWT access token for testing.

    Args:
        test_user_id: User ID to include in token.

    Returns:
        JWT access token string.
    """
    return create_access_token(str(test_user_id), scopes=["user"])


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """
    HTTP headers with valid authentication.

    Args:
        auth_token: JWT access token.

    Returns:
        Dictionary with Authorization header.
    """
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def mock_user_repository(test_user_data: dict[str, Any]) -> MagicMock:
    """
    Mock user repository for authentication testing.

    Args:
        test_user_data: Test user data to return.

    Returns:
        MagicMock configured as a user repository.
    """
    repo = MagicMock()

    # Create a mock user object
    mock_user = MagicMock()
    mock_user.id = test_user_data["id"]
    mock_user.email = test_user_data["email"]
    mock_user.password_hash = test_user_data["password_hash"]
    mock_user.name = test_user_data["name"]
    mock_user.is_active = test_user_data["is_active"]

    repo.get_by_email = AsyncMock(return_value=mock_user)
    repo.get_by_id = AsyncMock(return_value=mock_user)

    return repo


# =============================================================================
# Project-related fixtures
# =============================================================================


@pytest.fixture
def test_project_id() -> uuid.UUID:
    """
    Generate a consistent test project ID.

    Returns:
        UUID for test project.
    """
    return uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def other_user_id() -> uuid.UUID:
    """
    Generate a different user ID for ownership tests.

    Returns:
        UUID for a different test user.
    """
    return uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def other_project_id() -> uuid.UUID:
    """
    Generate ID for a project owned by another user.

    Returns:
        UUID for other user's project.
    """
    return uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture
def test_project(test_project_id: uuid.UUID, test_user_id: uuid.UUID) -> MagicMock:
    """
    Create a mock project owned by the test user.

    Args:
        test_project_id: Project UUID.
        test_user_id: Owner user UUID.

    Returns:
        MagicMock configured as a Project.
    """
    from datetime import datetime

    mock_project = MagicMock()
    mock_project.id = test_project_id
    mock_project.owner_id = test_user_id
    mock_project.name = "Test Project"
    mock_project.created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    mock_project.updated_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    mock_project.sites = []
    mock_project.competitors = []
    return mock_project


@pytest.fixture
def other_user_project(
    other_project_id: uuid.UUID, other_user_id: uuid.UUID
) -> MagicMock:
    """
    Create a mock project owned by a different user.

    Args:
        other_project_id: Project UUID.
        other_user_id: Owner user UUID.

    Returns:
        MagicMock configured as a Project owned by another user.
    """
    from datetime import datetime

    mock_project = MagicMock()
    mock_project.id = other_project_id
    mock_project.owner_id = other_user_id
    mock_project.name = "Other User Project"
    mock_project.created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    mock_project.updated_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    mock_project.sites = []
    mock_project.competitors = []
    return mock_project


@pytest.fixture
def test_site(test_project_id: uuid.UUID) -> MagicMock:
    """
    Create a mock site belonging to the test project.

    Args:
        test_project_id: Parent project UUID.

    Returns:
        MagicMock configured as a Site.
    """
    from datetime import datetime

    mock_site = MagicMock()
    mock_site.id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    mock_site.project_id = test_project_id
    mock_site.domain = "example.com"
    mock_site.base_url = "https://example.com"
    mock_site.created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    return mock_site


@pytest.fixture
def test_competitors(test_project_id: uuid.UUID) -> list[MagicMock]:
    """
    Create mock competitors for the test project.

    Args:
        test_project_id: Parent project UUID.

    Returns:
        List of MagicMocks configured as Competitors.
    """
    from datetime import datetime

    competitors = []
    for i, domain in enumerate(["competitor1.com", "competitor2.com"]):
        mock_competitor = MagicMock()
        mock_competitor.id = uuid.UUID(f"eeeeeeee-eeee-eeee-eeee-eeeeeeeeee{i:02d}")
        mock_competitor.project_id = test_project_id
        mock_competitor.domain = domain
        mock_competitor.created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        competitors.append(mock_competitor)
    return competitors
