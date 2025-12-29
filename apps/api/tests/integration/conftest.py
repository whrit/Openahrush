"""
Integration test fixtures for API testing.

Provides comprehensive fixtures for testing component interactions:
- Test database with real schema
- Fake Redis for queue testing
- Mock OAuth providers
- Mock S3/MinIO storage
- Test HTTP client with dependency overrides
"""

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fakeredis import aioredis as fakeredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

# Set test environment variables before importing app
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-at-least-32-characters-long")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-32-bytes-base64-encoded==")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")
os.environ.setdefault("S3_BUCKET", "test-bucket")

from semrush_core.config import Settings, get_settings
from semrush_core.database import get_async_session
from semrush_core.models import (
    CrawlRun,
    Export,
    IntegrationAccount,
    Project,
    Site,
    User,
    WebhookConfig,
)
from semrush_core.models.base import Base
from semrush_core.security.jwt import create_access_token
from semrush_core.security.password import hash_password

# =============================================================================
# Test Settings and Configuration
# =============================================================================


def get_test_settings() -> Settings:
    """
    Get test settings that override production settings.

    Returns:
        Settings configured for testing with in-memory database.
    """
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        jwt_secret="test-secret-key-that-is-at-least-32-characters-long",  # type: ignore[arg-type]
        encryption_key="test-encryption-key-32-bytes-base64-encoded==",  # type: ignore[arg-type]
        environment="development",
        debug=True,
        minio_endpoint="localhost:9000",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin",
        s3_bucket="test-bucket",
    )


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Configure anyio to use asyncio backend."""
    return "asyncio"


@pytest.fixture
def test_settings() -> Settings:
    """
    Fixture providing test settings.

    Returns:
        Test settings instance.
    """
    return get_test_settings()


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Create test database engine with in-memory SQLite.

    Yields:
        AsyncEngine configured for testing.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def test_db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create test database session with transaction rollback.

    Args:
        test_engine: Test database engine.

    Yields:
        AsyncSession for testing.
    """
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()


# =============================================================================
# Redis Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def fake_redis() -> AsyncGenerator[Any, None]:
    """
    Create fake Redis for testing queue operations.

    Yields:
        FakeRedis instance with async support.
    """
    redis = fakeredis.FakeRedis(decode_responses=True)
    yield redis
    await redis.flushall()
    await redis.aclose()


# =============================================================================
# HTTP Client Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def integration_client(
    test_db_session: AsyncSession,
    fake_redis: Any,
    test_settings: Settings,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create async HTTP client for integration testing.

    This client uses a real in-memory database and fake Redis,
    allowing tests to verify actual component interactions.

    Args:
        test_db_session: Test database session.
        fake_redis: Fake Redis instance.
        test_settings: Test settings.

    Yields:
        Configured async HTTP client.
    """
    from semrush_api.main import create_app

    app = create_app()

    # Override dependencies
    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        yield test_db_session

    def override_get_settings() -> Settings:
        return test_settings

    app.dependency_overrides[get_async_session] = override_get_async_session
    app.dependency_overrides[get_settings] = override_get_settings

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# =============================================================================
# User and Authentication Fixtures
# =============================================================================


@pytest.fixture
def test_user_id() -> uuid.UUID:
    """Generate a consistent test user ID."""
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def test_user_email() -> str:
    """Test user email address."""
    return "test@example.com"


@pytest.fixture
def test_user_password() -> str:
    """Test user password (plain text)."""
    return "testpassword123"


@pytest_asyncio.fixture
async def test_user(
    test_db_session: AsyncSession,
    test_user_id: uuid.UUID,
    test_user_email: str,
    test_user_password: str,
) -> User:
    """
    Create and persist a test user in the database.

    Args:
        test_db_session: Test database session.
        test_user_id: User UUID.
        test_user_email: User email.
        test_user_password: User password.

    Returns:
        Persisted User model.
    """
    user = User(
        id=test_user_id,
        email=test_user_email,
        password_hash=hash_password(test_user_password),
        name="Test User",
        is_active=True,
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


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


# =============================================================================
# Project and Site Fixtures
# =============================================================================


@pytest.fixture
def test_project_id() -> uuid.UUID:
    """Generate a consistent test project ID."""
    return uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest_asyncio.fixture
async def test_project(
    test_db_session: AsyncSession,
    test_user: User,
    test_project_id: uuid.UUID,
) -> Project:
    """
    Create and persist a test project.

    Args:
        test_db_session: Test database session.
        test_user: Parent user.
        test_project_id: Project UUID.

    Returns:
        Persisted Project model.
    """
    project = Project(
        id=test_project_id,
        owner_id=test_user.id,
        name="Test Project",
    )
    test_db_session.add(project)
    await test_db_session.commit()
    await test_db_session.refresh(project)
    return project


@pytest.fixture
def test_site_id() -> uuid.UUID:
    """Generate a consistent test site ID."""
    return uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


@pytest_asyncio.fixture
async def test_site(
    test_db_session: AsyncSession,
    test_project: Project,
    test_site_id: uuid.UUID,
) -> Site:
    """
    Create and persist a test site.

    Args:
        test_db_session: Test database session.
        test_project: Parent project.
        test_site_id: Site UUID.

    Returns:
        Persisted Site model.
    """
    site = Site(
        id=test_site_id,
        project_id=test_project.id,
        domain="example.com",
        base_url="https://example.com",
    )
    test_db_session.add(site)
    await test_db_session.commit()
    await test_db_session.refresh(site)
    return site


# =============================================================================
# OAuth Provider Fixtures
# =============================================================================


@pytest.fixture
def mock_oauth_tokens() -> dict[str, Any]:
    """Mock OAuth token response data."""
    return {
        "access_token": "mock_access_token_12345",
        "refresh_token": "mock_refresh_token_67890",
        "token_type": "Bearer",
        "expires_at": datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
        "scopes": ["email", "openid", "https://www.googleapis.com/auth/webmasters.readonly"],
    }


@pytest.fixture
def mock_oauth_user_info() -> dict[str, Any]:
    """Mock OAuth user info response."""
    return {
        "external_id": "external_user_123",
        "email": "oauth_user@example.com",
        "name": "OAuth Test User",
    }


@pytest.fixture
def mock_oauth_provider(
    mock_oauth_tokens: dict[str, Any],
    mock_oauth_user_info: dict[str, Any],
) -> MagicMock:
    """
    Create a mock OAuth provider for testing.

    Args:
        mock_oauth_tokens: Mock token response.
        mock_oauth_user_info: Mock user info response.

    Returns:
        MagicMock configured as an OAuth provider.
    """
    provider = AsyncMock()

    # Mock authorization URL generation
    provider.get_authorization_url = AsyncMock(
        return_value="https://accounts.google.com/o/oauth2/v2/auth?client_id=test&redirect_uri=http%3A%2F%2Ftest%2Fcallback&scope=email+openid&state=test_state&access_type=offline"
    )

    # Mock token exchange
    provider.exchange_code = AsyncMock(
        return_value=MagicMock(
            access_token=mock_oauth_tokens["access_token"],
            refresh_token=mock_oauth_tokens["refresh_token"],
            token_type=mock_oauth_tokens["token_type"],
            expires_at=mock_oauth_tokens["expires_at"],
            scopes=mock_oauth_tokens["scopes"],
        )
    )

    # Mock user info retrieval
    provider.get_user_info = AsyncMock(
        return_value=MagicMock(
            external_id=mock_oauth_user_info["external_id"],
            email=mock_oauth_user_info["email"],
            name=mock_oauth_user_info["name"],
        )
    )

    # Mock token refresh
    provider.refresh_access_token = AsyncMock(
        return_value=MagicMock(
            access_token="refreshed_access_token_12345",
            refresh_token=mock_oauth_tokens["refresh_token"],
            token_type=mock_oauth_tokens["token_type"],
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            scopes=mock_oauth_tokens["scopes"],
        )
    )

    # Mock token revocation
    provider.revoke_token = AsyncMock(return_value=True)

    return provider


# =============================================================================
# Integration Account Fixtures
# =============================================================================


@pytest.fixture
def test_integration_account_id() -> uuid.UUID:
    """Generate a test integration account ID."""
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest_asyncio.fixture
async def test_integration_account(
    test_db_session: AsyncSession,
    test_user: User,
    test_integration_account_id: uuid.UUID,
) -> IntegrationAccount:
    """
    Create and persist a test integration account.

    Args:
        test_db_session: Test database session.
        test_user: Parent user.
        test_integration_account_id: Integration account UUID.

    Returns:
        Persisted IntegrationAccount model.
    """
    account = IntegrationAccount(
        id=test_integration_account_id,
        user_id=test_user.id,
        provider="google_search_console",
        provider_account_id="external_user_123",
        token_expires_at=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
        scopes=["email", "openid"],
        last_sync_at=None,
        sync_status="pending",
        sync_error=None,
    )
    test_db_session.add(account)
    await test_db_session.commit()
    await test_db_session.refresh(account)
    return account


# =============================================================================
# Crawl Fixtures
# =============================================================================


@pytest.fixture
def test_crawl_run_id() -> uuid.UUID:
    """Generate a test crawl run ID."""
    return uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest_asyncio.fixture
async def test_crawl_run(
    test_db_session: AsyncSession,
    test_project: Project,
    test_site: Site,
    test_crawl_run_id: uuid.UUID,
) -> CrawlRun:
    """
    Create and persist a test crawl run.

    Args:
        test_db_session: Test database session.
        test_project: Parent project.
        test_site: Target site.
        test_crawl_run_id: Crawl run UUID.

    Returns:
        Persisted CrawlRun model.
    """
    crawl_run = CrawlRun(
        id=test_crawl_run_id,
        project_id=test_project.id,
        site_id=test_site.id,
        status="queued",
        config_snapshot={"max_pages": 100, "follow_external_links": False},
    )
    test_db_session.add(crawl_run)
    await test_db_session.commit()
    await test_db_session.refresh(crawl_run)
    return crawl_run


# =============================================================================
# Export Fixtures
# =============================================================================


@pytest.fixture
def test_export_id() -> uuid.UUID:
    """Generate a test export ID."""
    return uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


@pytest_asyncio.fixture
async def test_export(
    test_db_session: AsyncSession,
    test_project: Project,
    test_export_id: uuid.UUID,
) -> Export:
    """
    Create and persist a test export.

    Args:
        test_db_session: Test database session.
        test_project: Parent project.
        test_export_id: Export UUID.

    Returns:
        Persisted Export model.
    """
    export = Export(
        id=test_export_id,
        project_id=test_project.id,
        format="csv",
        resource="issues",
        status="queued",
        params={},
    )
    test_db_session.add(export)
    await test_db_session.commit()
    await test_db_session.refresh(export)
    return export


# =============================================================================
# Webhook Fixtures
# =============================================================================


@pytest.fixture
def test_webhook_config_id() -> uuid.UUID:
    """Generate a test webhook config ID."""
    return uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


@pytest_asyncio.fixture
async def test_webhook_config(
    test_db_session: AsyncSession,
    test_project: Project,
    test_webhook_config_id: uuid.UUID,
) -> WebhookConfig:
    """
    Create and persist a test webhook configuration.

    Args:
        test_db_session: Test database session.
        test_project: Parent project.
        test_webhook_config_id: Webhook config UUID.

    Returns:
        Persisted WebhookConfig model.
    """
    webhook = WebhookConfig(
        id=test_webhook_config_id,
        project_id=test_project.id,
        url="https://example.com/webhook",
        secret="encrypted_webhook_secret",
        enabled_events=["crawl.completed", "alert.fired"],
        is_enabled=True,
    )
    test_db_session.add(webhook)
    await test_db_session.commit()
    await test_db_session.refresh(webhook)
    return webhook


@pytest.fixture
def test_webhook_delivery_id() -> uuid.UUID:
    """Generate a test webhook delivery ID."""
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


# =============================================================================
# MinIO/S3 Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_minio_client() -> MagicMock:
    """
    Create a mock MinIO client for testing storage operations.

    Returns:
        MagicMock configured as a MinIO client.
    """
    client = MagicMock()

    # Mock bucket operations
    client.bucket_exists = MagicMock(return_value=True)
    client.make_bucket = MagicMock()

    # Mock object operations with dynamic return values
    def mock_put_object(bucket_name, object_name, **kwargs):
        result = MagicMock()
        result.bucket_name = bucket_name
        result.object_name = object_name
        result.etag = "test-etag"
        return result

    client.put_object = MagicMock(side_effect=mock_put_object)
    client.get_object = MagicMock(
        return_value=MagicMock(
            read=MagicMock(return_value=b"test data"),
            release_conn=MagicMock(),
        )
    )
    client.presigned_get_object = MagicMock(
        return_value="https://localhost:9000/test-bucket/test-object?X-Amz-Signature=test"
    )
    client.remove_object = MagicMock()

    return client


# =============================================================================
# HTTP Request Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_httpx_response() -> MagicMock:
    """
    Create a mock HTTP response for testing webhook delivery.

    Returns:
        MagicMock configured as an HTTPX response.
    """
    response = MagicMock()
    response.status_code = 200
    response.text = '{"success": true}'
    response.headers = {"content-type": "application/json"}
    response.raise_for_status = MagicMock()
    return response
