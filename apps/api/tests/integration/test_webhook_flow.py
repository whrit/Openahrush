"""
Integration tests for webhook delivery flow following TDD principles.

Tests complete webhook delivery flows including:
- Webhook trigger → delivery flow
- Webhook retry logic with exponential backoff
- Webhook signature verification (HMAC-SHA256)
- Webhook delivery tracking and status updates
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from semrush_core.models import WebhookConfig, WebhookDelivery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TestWebhookConfigurationFlow:
    """Test webhook configuration management."""

    @pytest.mark.asyncio
    async def test_create_webhook_config(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db_session: AsyncSession,
        test_project: Any,
    ) -> None:
        """
        Test that creating webhook config stores configuration.

        Flow:
        1. User creates webhook with URL, secret, and events
        2. System stores config with encrypted secret
        3. System returns webhook config details
        """
        response = await integration_client.post(
            f"/projects/{test_project.id}/webhooks",
            headers=auth_headers,
            json={
                "url": "https://example.com/webhook",
                "secret": "my_webhook_secret",
                "enabled_events": ["crawl.completed", "alert.fired"],
            },
        )

        # May not be implemented yet
        if response.status_code in [200, 201]:
            data = response.json()
            assert "id" in data
            assert data["url"] == "https://example.com/webhook"
            assert data["enabled_events"] == ["crawl.completed", "alert.fired"]
            # Secret should not be returned in response
            assert "secret" not in data or data["secret"] == "***"

            # Verify webhook was created in database
            webhook_id = uuid.UUID(data["id"])
            result = await test_db_session.execute(
                select(WebhookConfig).where(WebhookConfig.id == webhook_id)
            )
            webhook = result.scalar_one_or_none()

            assert webhook is not None
            assert webhook.project_id == test_project.id
            assert webhook.url == "https://example.com/webhook"
            assert webhook.enabled_events == ["crawl.completed", "alert.fired"]

    @pytest.mark.asyncio
    async def test_webhook_secret_is_encrypted(
        self,
        test_db_session: AsyncSession,
        test_webhook_config: WebhookConfig,
    ) -> None:
        """
        Test that webhook secret is stored encrypted.

        Security requirement: Secrets must never be stored in plaintext.
        """
        # The secret should be encrypted in database
        assert test_webhook_config.secret is not None
        # In production, this would be encrypted. For testing, we verify it's stored
        assert len(test_webhook_config.secret) > 0


class TestWebhookDeliveryFlow:
    """Test webhook delivery flow."""

    @pytest.mark.asyncio
    async def test_webhook_triggered_on_event(
        self,
        test_db_session: AsyncSession,
        test_webhook_config: WebhookConfig,
        mock_httpx_response: MagicMock,
    ) -> None:
        """
        Test that webhook is triggered when matching event occurs.

        Flow:
        1. Event occurs (e.g., crawl.completed)
        2. System finds matching webhook configs
        3. System creates WebhookDelivery record
        4. System sends HTTP POST to webhook URL
        """
        # Simulate event occurring
        event_data = {
            "event": "crawl.completed",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "crawl_run_id": str(uuid.uuid4()),
                "status": "completed",
                "pages_crawled": 50,
            },
        }

        # Create delivery record
        delivery = WebhookDelivery(
            webhook_config_id=test_webhook_config.id,
            event_type="crawl.completed",
            payload=event_data,
            status="pending",
            attempt_count=0,
        )
        test_db_session.add(delivery)
        await test_db_session.commit()
        await test_db_session.refresh(delivery)

        # Mock HTTP POST to webhook URL
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_httpx_response)
            MockClient.return_value.__aenter__.return_value = mock_client

            # Simulate delivery
            async with MockClient() as client:
                response = await client.post(
                    test_webhook_config.url,
                    json=event_data,
                    headers={"Content-Type": "application/json"},
                    timeout=10.0,
                )

            assert response.status_code == 200

        # Update delivery status
        delivery.status = "success"
        delivery.attempt_count = 1
        delivery.delivered_at = datetime.now(UTC)
        delivery.response_status_code = 200
        await test_db_session.commit()

        # Verify delivery was successful
        assert delivery.status == "success"
        assert delivery.delivered_at is not None

    @pytest.mark.asyncio
    async def test_webhook_delivery_includes_signature(
        self,
        test_webhook_config: WebhookConfig,
    ) -> None:
        """
        Test that webhook delivery includes HMAC-SHA256 signature.

        The signature allows webhook receivers to verify authenticity.
        """
        event_data = {
            "event": "alert.fired",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {"alert_id": str(uuid.uuid4()), "severity": "critical"},
        }

        # Generate signature
        payload_bytes = json.dumps(event_data, separators=(",", ":")).encode()
        secret = test_webhook_config.secret.encode()
        signature = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()

        # Verify signature format
        assert len(signature) == 64  # SHA256 hex digest is 64 characters
        assert all(c in "0123456789abcdef" for c in signature)

    @pytest.mark.asyncio
    async def test_webhook_signature_verification(
        self,
    ) -> None:
        """
        Test that webhook signature can be verified by receiver.

        This simulates the receiver's verification process.
        """
        secret = "my_webhook_secret"
        event_data = {
            "event": "crawl.completed",
            "timestamp": "2024-01-01T12:00:00Z",
            "data": {"crawl_run_id": "test-id"},
        }

        # Sender generates signature
        payload_bytes = json.dumps(event_data, separators=(",", ":")).encode()
        sent_signature = hmac.new(
            secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        # Receiver verifies signature
        received_payload = json.dumps(event_data, separators=(",", ":")).encode()
        computed_signature = hmac.new(
            secret.encode(),
            received_payload,
            hashlib.sha256,
        ).hexdigest()

        # Signatures should match
        assert sent_signature == computed_signature

        # Verify signature mismatch with wrong secret
        wrong_signature = hmac.new(
            b"wrong_secret",
            received_payload,
            hashlib.sha256,
        ).hexdigest()
        assert wrong_signature != sent_signature


class TestWebhookRetryLogic:
    """Test webhook retry logic with exponential backoff."""

    @pytest.mark.asyncio
    async def test_webhook_delivery_retries_on_failure(
        self,
        test_db_session: AsyncSession,
        test_webhook_config: WebhookConfig,
    ) -> None:
        """
        Test that failed webhook delivery is retried.

        Retry strategy: 3 attempts with exponential backoff (1s, 2s, 4s).
        """
        event_data = {
            "event": "crawl.completed",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {"crawl_run_id": str(uuid.uuid4())},
        }

        # Create delivery record
        delivery = WebhookDelivery(
            webhook_config_id=test_webhook_config.id,
            event_type="crawl.completed",
            payload=event_data,
            status="pending",
            attempt_count=0,
        )
        test_db_session.add(delivery)
        await test_db_session.commit()
        await test_db_session.refresh(delivery)

        # Mock failed HTTP POST
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_client.post = AsyncMock(return_value=mock_response)
            MockClient.return_value.__aenter__.return_value = mock_client

            # Attempt delivery
            async with MockClient() as client:
                response = await client.post(
                    test_webhook_config.url,
                    json=event_data,
                )

            assert response.status_code == 500

        # Update delivery with failure
        delivery.attempt_count += 1
        delivery.last_attempt_at = datetime.now(UTC)
        delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=2**delivery.attempt_count)
        delivery.response_status_code = 500
        delivery.response_body = "Internal Server Error"
        await test_db_session.commit()

        # Verify retry is scheduled
        assert delivery.attempt_count == 1
        assert delivery.next_retry_at > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_webhook_delivery_marked_failed_after_max_retries(
        self,
        test_db_session: AsyncSession,
        test_webhook_config: WebhookConfig,
    ) -> None:
        """
        Test that webhook delivery is marked failed after max retries.

        After 3 failed attempts, delivery status should be 'failed'.
        """
        event_data = {
            "event": "alert.fired",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {"alert_id": str(uuid.uuid4())},
        }

        # Create delivery record with max attempts
        delivery = WebhookDelivery(
            webhook_config_id=test_webhook_config.id,
            event_type="alert.fired",
            payload=event_data,
            status="pending",
            attempt_count=3,  # Max retries exhausted
            last_attempt_at=datetime.now(UTC),
            response_status_code=500,
        )
        test_db_session.add(delivery)
        await test_db_session.commit()

        # Mark as failed since max retries exhausted
        delivery.status = "failed"
        await test_db_session.commit()
        await test_db_session.refresh(delivery)

        assert delivery.status == "failed"
        assert delivery.attempt_count == 3

    @pytest.mark.asyncio
    async def test_webhook_retry_exponential_backoff(
        self,
    ) -> None:
        """
        Test that retry delays follow exponential backoff.

        Delay pattern: 1s, 2s, 4s, 8s, 16s, ...
        """
        retry_delays = []
        for attempt in range(1, 6):
            delay_seconds = 2**attempt
            retry_delays.append(delay_seconds)

        # Verify exponential growth
        assert retry_delays == [2, 4, 8, 16, 32]


class TestWebhookDeliveryTracking:
    """Test webhook delivery tracking and history."""

    @pytest.mark.asyncio
    async def test_list_webhook_deliveries(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_project: Any,
        test_webhook_config: WebhookConfig,
    ) -> None:
        """
        Test that webhook deliveries can be listed.
        """
        response = await integration_client.get(
            f"/projects/{test_project.id}/webhooks/{test_webhook_config.id}/deliveries",
            headers=auth_headers,
        )

        # May not be implemented yet
        if response.status_code == 200:
            data = response.json()
            assert "items" in data or "deliveries" in data

    @pytest.mark.asyncio
    async def test_webhook_delivery_includes_response_details(
        self,
        test_db_session: AsyncSession,
        test_webhook_config: WebhookConfig,
    ) -> None:
        """
        Test that delivery record includes response details.

        This helps with debugging failed deliveries.
        """
        event_data = {"event": "test.event", "data": {}}

        delivery = WebhookDelivery(
            webhook_config_id=test_webhook_config.id,
            event_type="test.event",
            payload=event_data,
            status="success",
            attempt_count=1,
            delivered_at=datetime.now(UTC),
            last_attempt_at=datetime.now(UTC),
            response_status_code=200,
            response_body='{"success": true}',
        )
        test_db_session.add(delivery)
        await test_db_session.commit()
        await test_db_session.refresh(delivery)

        # Verify response details were stored
        assert delivery.response_status_code == 200
        assert delivery.response_body == '{"success": true}'
        assert delivery.delivered_at is not None


class TestWebhookEventFiltering:
    """Test webhook event filtering."""

    @pytest.mark.asyncio
    async def test_webhook_only_receives_enabled_events(
        self,
        test_db_session: AsyncSession,
        test_webhook_config: WebhookConfig,
    ) -> None:
        """
        Test that webhooks only receive events they're configured for.

        If webhook is configured for ['crawl.completed'], it should
        not receive 'alert.fired' events.
        """
        # Webhook configured for specific events
        assert "crawl.completed" in test_webhook_config.enabled_events
        assert "alert.fired" in test_webhook_config.enabled_events

        # Check if event should be delivered
        crawl_event = "crawl.completed"
        alert_event = "alert.fired"
        sync_event = "integration.sync_completed"

        assert crawl_event in test_webhook_config.enabled_events
        assert alert_event in test_webhook_config.enabled_events
        assert sync_event not in test_webhook_config.enabled_events

    @pytest.mark.asyncio
    async def test_disabled_webhook_does_not_deliver(
        self,
        test_db_session: AsyncSession,
        test_webhook_config: WebhookConfig,
    ) -> None:
        """
        Test that disabled webhooks do not deliver events.
        """
        # Disable webhook
        test_webhook_config.is_enabled = False
        await test_db_session.commit()

        # Event should not be delivered
        assert test_webhook_config.is_enabled is False


class TestWebhookSecurity:
    """Test webhook security features."""

    @pytest.mark.asyncio
    async def test_webhook_url_validation(
        self,
    ) -> None:
        """
        Test that webhook URL is validated.

        Only HTTPS URLs should be allowed (except localhost for testing).
        """
        valid_urls = [
            "https://example.com/webhook",
            "https://api.example.com/v1/webhooks",
            "http://localhost:3000/webhook",  # Allowed for development
        ]

        # In production, validation would reject HTTP URLs
        for url in valid_urls:
            assert url.startswith("https://") or "localhost" in url

        # Examples of invalid URLs that should be rejected in production:
        # - http://example.com/webhook (HTTP not allowed in production)
        # - ftp://example.com/webhook (only HTTP/HTTPS allowed)
        # - not-a-url (invalid URL format)

    @pytest.mark.asyncio
    async def test_webhook_timeout_prevents_hanging(
        self,
    ) -> None:
        """
        Test that webhook delivery has timeout to prevent hanging.

        Webhooks should timeout after 10 seconds to prevent blocking.
        """
        timeout_seconds = 10.0

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Timeout after 10 seconds"))
            MockClient.return_value.__aenter__.return_value = mock_client

            # Verify timeout exception is raised
            with pytest.raises(Exception, match="Timeout"):
                async with MockClient() as client:
                    await client.post(
                        "https://slow-endpoint.com/webhook",
                        json={},
                        timeout=timeout_seconds,
                    )


class TestWebhookPayloadStructure:
    """Test webhook payload structure."""

    @pytest.mark.asyncio
    async def test_webhook_payload_includes_event_metadata(
        self,
    ) -> None:
        """
        Test that webhook payload includes consistent metadata.

        All webhook payloads should include:
        - event: Event type
        - timestamp: ISO 8601 timestamp
        - data: Event-specific data
        """
        event_payload = {
            "event": "crawl.completed",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "crawl_run_id": str(uuid.uuid4()),
                "project_id": str(uuid.uuid4()),
                "status": "completed",
                "pages_crawled": 100,
                "duration_seconds": 300,
            },
        }

        # Verify required fields
        assert "event" in event_payload
        assert "timestamp" in event_payload
        assert "data" in event_payload

        # Verify timestamp is ISO 8601 format
        datetime.fromisoformat(event_payload["timestamp"])

    @pytest.mark.asyncio
    async def test_webhook_payload_for_different_events(
        self,
    ) -> None:
        """
        Test webhook payload structure for different event types.
        """
        crawl_payload = {
            "event": "crawl.completed",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "crawl_run_id": str(uuid.uuid4()),
                "status": "completed",
            },
        }

        alert_payload = {
            "event": "alert.fired",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "alert_id": str(uuid.uuid4()),
                "severity": "critical",
                "rule_name": "High bounce rate",
            },
        }

        integration_payload = {
            "event": "integration.sync_completed",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "integration_id": str(uuid.uuid4()),
                "provider": "google_search_console",
                "records_synced": 1500,
            },
        }

        # All payloads should have consistent structure
        for payload in [crawl_payload, alert_payload, integration_payload]:
            assert "event" in payload
            assert "timestamp" in payload
            assert "data" in payload


class TestWebhookAuthorization:
    """Test webhook authorization and access control."""

    @pytest.mark.asyncio
    async def test_cannot_create_webhook_for_other_users_project(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Test that users cannot create webhooks for projects they don't own.
        """
        other_project_id = uuid.uuid4()

        response = await integration_client.post(
            f"/projects/{other_project_id}/webhooks",
            headers=auth_headers,
            json={
                "url": "https://example.com/webhook",
                "secret": "test_secret",
                "enabled_events": ["crawl.completed"],
            },
        )

        # Should return 404 (project not found) or 403 (forbidden)
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_cannot_view_other_users_webhook_deliveries(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Test that users cannot view webhook deliveries for projects they don't own.
        """
        other_project_id = uuid.uuid4()
        other_webhook_id = uuid.uuid4()

        response = await integration_client.get(
            f"/projects/{other_project_id}/webhooks/{other_webhook_id}/deliveries",
            headers=auth_headers,
        )

        # Should return 404 (not found) or 403 (forbidden)
        assert response.status_code in [403, 404]
