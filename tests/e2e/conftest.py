"""
Pytest fixtures for E2E API testing with Playwright.

Provides:
- Playwright API request context for E2E testing
- Real API server connectivity checks
- Authentication helpers (user registration, login, JWT)
- Cleanup fixtures for test data
- Skip markers for when API is not running
"""

import contextlib
import os
import uuid
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from playwright.async_api import APIRequestContext, Playwright, async_playwright

# Default API base URL - can be overridden via environment variable
API_BASE_URL = os.getenv("E2E_API_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """
    Get the base URL for the API server.

    Returns:
        Base URL for API (default: http://localhost:8000).
    """
    return API_BASE_URL


@pytest_asyncio.fixture(scope="session")
async def playwright_instance() -> AsyncGenerator[Playwright, None]:
    """
    Create a Playwright instance for the test session.

    Yields:
        Playwright instance.
    """
    async with async_playwright() as playwright:
        yield playwright


@pytest_asyncio.fixture
async def api_context(
    playwright_instance: Playwright,
    api_base_url: str,
) -> AsyncGenerator[APIRequestContext, None]:
    """
    Create a Playwright APIRequestContext for making HTTP requests.

    Args:
        playwright_instance: Playwright instance.
        api_base_url: Base URL for the API.

    Yields:
        APIRequestContext for HTTP requests.
    """
    context = await playwright_instance.request.new_context(
        base_url=api_base_url,
        extra_http_headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    yield context
    await context.dispose()


async def check_api_health(api_base_url: str) -> bool:
    """
    Check if the API server is running and healthy.

    Args:
        api_base_url: Base URL for the API.

    Returns:
        True if API is healthy, False otherwise.
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{api_base_url}/health")
            return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def skip_if_api_unavailable(api_base_url: str) -> None:
    """
    Skip test if API server is not available.

    Args:
        api_base_url: Base URL for the API.

    Raises:
        pytest.skip: If API is not available.
    """
    import asyncio

    is_healthy = asyncio.run(check_api_health(api_base_url))
    if not is_healthy:
        pytest.skip(f"API server not available at {api_base_url}")


@pytest_asyncio.fixture
async def test_user(
    api_context: APIRequestContext,
    skip_if_api_unavailable: None,
) -> dict[str, str]:
    """
    Create a test user and return credentials.

    Args:
        api_context: Playwright API request context.
        skip_if_api_unavailable: Ensures API is available.

    Returns:
        Dictionary with email and password.
    """
    # Generate unique email to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    email = f"test-{unique_id}@example.com"
    password = "testpassword123"

    # Register user
    response = await api_context.post(
        "/auth/register",
        data={
            "email": email,
            "password": password,
            "name": f"Test User {unique_id}",
        },
    )

    if response.status != 201:
        error_text = await response.text()
        raise RuntimeError(f"Failed to create test user: {response.status} - {error_text}")

    return {"email": email, "password": password}


@pytest_asyncio.fixture
async def auth_token(
    api_context: APIRequestContext,
    test_user: dict[str, str],
) -> str:
    """
    Authenticate and return JWT access token.

    Args:
        api_context: Playwright API request context.
        test_user: Test user credentials.

    Returns:
        JWT access token.
    """
    response = await api_context.post(
        "/auth/login",
        data={
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )

    if response.status != 200:
        error_text = await response.text()
        raise RuntimeError(f"Failed to authenticate: {response.status} - {error_text}")

    data = await response.json()
    return data["access_token"]


@pytest_asyncio.fixture
async def auth_context(
    playwright_instance: Playwright,
    api_base_url: str,
    auth_token: str,
) -> AsyncGenerator[APIRequestContext, None]:
    """
    Create an authenticated Playwright APIRequestContext.

    Args:
        playwright_instance: Playwright instance.
        api_base_url: Base URL for the API.
        auth_token: JWT access token.

    Yields:
        Authenticated APIRequestContext.
    """
    context = await playwright_instance.request.new_context(
        base_url=api_base_url,
        extra_http_headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {auth_token}",
        },
    )
    yield context
    await context.dispose()


@pytest_asyncio.fixture
async def test_project(
    auth_context: APIRequestContext,
) -> AsyncGenerator[dict, None]:
    """
    Create a test project.

    Args:
        auth_context: Authenticated API request context.

    Yields:
        Project data, then cleans up after test.
    """
    # Create project
    response = await auth_context.post(
        "/projects",
        data={"name": f"Test Project {uuid.uuid4()}"},
    )

    if response.status != 201:
        error_text = await response.text()
        raise RuntimeError(f"Failed to create test project: {response.status} - {error_text}")

    project = await response.json()

    yield project

    # Cleanup: delete project after test
    with contextlib.suppress(Exception):
        await auth_context.delete(f"/projects/{project['id']}")
