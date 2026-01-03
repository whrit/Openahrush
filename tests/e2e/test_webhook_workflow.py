"""
E2E tests for webhook workflow.

Tests the complete webhook workflow:
- Webhook configuration
- Webhook testing
- Webhook delivery verification
"""

import uuid

import pytest
from playwright.async_api import APIRequestContext

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
]


class TestWebhookWorkflow:
    """Test the complete webhook workflow."""

    async def test_create_webhook(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test webhook creation."""
        webhook_url = "https://webhook.site/test-endpoint"

        response = await auth_context.post(
            f"/projects/{test_project['id']}/webhooks",
            data={
                "url": webhook_url,
                "events": ["crawl.completed", "issues.created"],
                "secret": "test-secret-key",
            },
        )

        assert response.status == 201
        data = await response.json()
        assert data["url"] == webhook_url
        assert "id" in data
        assert "events" in data

    async def test_list_webhooks(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test listing webhooks for a project."""
        # First create a webhook
        await auth_context.post(
            f"/projects/{test_project['id']}/webhooks",
            data={
                "url": "https://example.com/webhook",
                "events": ["crawl.completed"],
            },
        )

        response = await auth_context.get(
            f"/projects/{test_project['id']}/webhooks",
        )

        assert response.status == 200
        data = await response.json()
        assert isinstance(data, list)

    async def test_get_webhook(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test getting a single webhook."""
        # Create a webhook first
        create_response = await auth_context.post(
            f"/projects/{test_project['id']}/webhooks",
            data={
                "url": "https://example.com/webhook",
                "events": ["issues.created"],
            },
        )
        webhook = await create_response.json()

        # Get the webhook
        response = await auth_context.get(
            f"/projects/{test_project['id']}/webhooks/{webhook['id']}",
        )

        assert response.status == 200
        data = await response.json()
        assert data["id"] == webhook["id"]

    async def test_update_webhook(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test updating a webhook."""
        # Create a webhook first
        create_response = await auth_context.post(
            f"/projects/{test_project['id']}/webhooks",
            data={
                "url": "https://example.com/webhook",
                "events": ["crawl.completed"],
            },
        )
        webhook = await create_response.json()

        # Update the webhook
        new_url = "https://example.com/new-webhook"
        response = await auth_context.patch(
            f"/projects/{test_project['id']}/webhooks/{webhook['id']}",
            data={
                "url": new_url,
                "events": ["crawl.completed", "issues.created"],
            },
        )

        assert response.status == 200
        data = await response.json()
        assert data["url"] == new_url

    async def test_delete_webhook(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test deleting a webhook."""
        # Create a webhook first
        create_response = await auth_context.post(
            f"/projects/{test_project['id']}/webhooks",
            data={
                "url": "https://example.com/webhook-to-delete",
                "events": ["crawl.completed"],
            },
        )
        webhook = await create_response.json()

        # Delete the webhook
        delete_response = await auth_context.delete(
            f"/projects/{test_project['id']}/webhooks/{webhook['id']}",
        )

        assert delete_response.status == 204

        # Verify it's deleted
        get_response = await auth_context.get(
            f"/projects/{test_project['id']}/webhooks/{webhook['id']}",
        )
        assert get_response.status == 404


class TestWebhookValidation:
    """Test webhook input validation."""

    async def test_create_webhook_invalid_url(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test that invalid webhook URL is rejected."""
        response = await auth_context.post(
            f"/projects/{test_project['id']}/webhooks",
            data={
                "url": "not-a-valid-url",
                "events": ["crawl.completed"],
            },
        )

        assert response.status == 422

    async def test_create_webhook_missing_events(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test that webhook without events is rejected."""
        response = await auth_context.post(
            f"/projects/{test_project['id']}/webhooks",
            data={
                "url": "https://example.com/webhook",
            },
        )

        assert response.status == 422

    async def test_get_nonexistent_webhook(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test getting a nonexistent webhook returns 404."""
        fake_id = str(uuid.uuid4())
        response = await auth_context.get(
            f"/projects/{test_project['id']}/webhooks/{fake_id}",
        )

        assert response.status == 404


class TestWebhookDeliveries:
    """Test webhook delivery history."""

    async def test_list_webhook_deliveries(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test listing webhook deliveries."""
        # Create a webhook first
        create_response = await auth_context.post(
            f"/projects/{test_project['id']}/webhooks",
            data={
                "url": "https://example.com/webhook",
                "events": ["crawl.completed"],
            },
        )
        webhook = await create_response.json()

        # Get deliveries
        response = await auth_context.get(
            f"/projects/{test_project['id']}/webhooks/{webhook['id']}/deliveries",
        )

        assert response.status == 200
        data = await response.json()
        assert isinstance(data, list)

    async def test_test_webhook(
        self,
        auth_context: APIRequestContext,
        test_project: dict,
    ) -> None:
        """Test sending a test webhook."""
        # Create a webhook first
        create_response = await auth_context.post(
            f"/projects/{test_project['id']}/webhooks",
            data={
                "url": "https://webhook.site/test",
                "events": ["crawl.completed"],
            },
        )
        webhook = await create_response.json()

        # Send test webhook
        response = await auth_context.post(
            f"/projects/{test_project['id']}/webhooks/{webhook['id']}/test",
        )

        # Should accept the test request (even if delivery fails)
        assert response.status in [200, 202]
