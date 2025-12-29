"""
Tests for webhook signature and delivery modules.

Following TDD: Tests written first, then implementation.

Tests cover:
- Webhook signature generation (HMAC-SHA256)
- Webhook signature verification with timestamp tolerance
- Webhook delivery retry scheduling with exponential backoff
- Max retries exceeded handling
- Backoff delay correctness
"""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from semrush_core.models.webhook import DeliveryStatus, WebhookConfig, WebhookDelivery

# =============================================================================
# Webhook Signature Tests
# =============================================================================


class TestWebhookSignatureGeneration:
    """Tests for webhook signature generation."""

    def test_generate_signature_returns_string(self):
        """generate_signature should return a formatted signature string."""
        from semrush_core.webhooks.signature import generate_signature

        payload = '{"event": "test"}'
        secret = "test_secret_key"

        signature = generate_signature(payload, secret)

        assert isinstance(signature, str)
        assert signature.startswith("t=")
        assert ",v1=" in signature

    def test_generate_signature_with_explicit_timestamp(self):
        """generate_signature should use provided timestamp."""
        from semrush_core.webhooks.signature import generate_signature

        payload = '{"event": "test"}'
        secret = "test_secret_key"
        timestamp = 1234567890

        signature = generate_signature(payload, secret, timestamp)

        assert f"t={timestamp}" in signature

    def test_generate_signature_uses_current_time_when_not_provided(self):
        """generate_signature should use current time when timestamp not provided."""
        from semrush_core.webhooks.signature import generate_signature

        payload = '{"event": "test"}'
        secret = "test_secret_key"
        now = int(time.time())

        signature = generate_signature(payload, secret)

        # Extract timestamp from signature
        parts = dict(p.split("=") for p in signature.split(","))
        sig_timestamp = int(parts["t"])

        # Should be within 1 second of now
        assert abs(sig_timestamp - now) <= 1

    def test_generate_signature_deterministic_with_same_inputs(self):
        """generate_signature should produce same output for same inputs."""
        from semrush_core.webhooks.signature import generate_signature

        payload = '{"event": "test"}'
        secret = "test_secret_key"
        timestamp = 1234567890

        sig1 = generate_signature(payload, secret, timestamp)
        sig2 = generate_signature(payload, secret, timestamp)

        assert sig1 == sig2

    def test_generate_signature_different_with_different_payloads(self):
        """generate_signature should produce different output for different payloads."""
        from semrush_core.webhooks.signature import generate_signature

        secret = "test_secret_key"
        timestamp = 1234567890

        sig1 = generate_signature('{"event": "test1"}', secret, timestamp)
        sig2 = generate_signature('{"event": "test2"}', secret, timestamp)

        assert sig1 != sig2

    def test_generate_signature_different_with_different_secrets(self):
        """generate_signature should produce different output for different secrets."""
        from semrush_core.webhooks.signature import generate_signature

        payload = '{"event": "test"}'
        timestamp = 1234567890

        sig1 = generate_signature(payload, "secret1", timestamp)
        sig2 = generate_signature(payload, "secret2", timestamp)

        assert sig1 != sig2

    def test_generate_signature_format(self):
        """generate_signature should produce correctly formatted signature."""
        from semrush_core.webhooks.signature import generate_signature

        payload = '{"event": "test"}'
        secret = "test_secret"
        timestamp = 1234567890

        signature = generate_signature(payload, secret, timestamp)

        # Should have format: t=<timestamp>,v1=<hex_signature>
        parts = signature.split(",")
        assert len(parts) == 2
        assert parts[0].startswith("t=")
        assert parts[1].startswith("v1=")

        # v1 should be a 64-character hex string (SHA256)
        hex_sig = parts[1].split("=")[1]
        assert len(hex_sig) == 64
        assert all(c in "0123456789abcdef" for c in hex_sig)


class TestWebhookSignatureVerification:
    """Tests for webhook signature verification."""

    def test_verify_signature_valid(self):
        """verify_signature should return True for valid signature."""
        from semrush_core.webhooks.signature import generate_signature, verify_signature

        payload = '{"event": "test"}'
        secret = "test_secret_key"
        timestamp = int(time.time())

        signature = generate_signature(payload, secret, timestamp)

        assert verify_signature(payload, secret, signature) is True

    def test_verify_signature_invalid_signature(self):
        """verify_signature should return False for tampered signature."""
        from semrush_core.webhooks.signature import verify_signature

        payload = '{"event": "test"}'
        secret = "test_secret_key"
        timestamp = int(time.time())

        # Create a fake signature
        fake_signature = (
            f"t={timestamp},v1=0000000000000000000000000000000000000000000000000000000000000000"
        )

        assert verify_signature(payload, secret, fake_signature) is False

    def test_verify_signature_invalid_payload(self):
        """verify_signature should return False for modified payload."""
        from semrush_core.webhooks.signature import generate_signature, verify_signature

        secret = "test_secret_key"
        timestamp = int(time.time())

        original_payload = '{"event": "test"}'
        modified_payload = '{"event": "hacked"}'

        signature = generate_signature(original_payload, secret, timestamp)

        assert verify_signature(modified_payload, secret, signature) is False

    def test_verify_signature_wrong_secret(self):
        """verify_signature should return False for wrong secret."""
        from semrush_core.webhooks.signature import generate_signature, verify_signature

        payload = '{"event": "test"}'
        timestamp = int(time.time())

        signature = generate_signature(payload, "correct_secret", timestamp)

        assert verify_signature(payload, "wrong_secret", signature) is False

    def test_verify_signature_expired_timestamp(self):
        """verify_signature should return False for expired timestamp."""
        from semrush_core.webhooks.signature import generate_signature, verify_signature

        payload = '{"event": "test"}'
        secret = "test_secret_key"
        # 10 minutes ago (beyond default 5 minute tolerance)
        old_timestamp = int(time.time()) - 600

        signature = generate_signature(payload, secret, old_timestamp)

        assert verify_signature(payload, secret, signature) is False

    def test_verify_signature_future_timestamp(self):
        """verify_signature should return False for future timestamp beyond tolerance."""
        from semrush_core.webhooks.signature import generate_signature, verify_signature

        payload = '{"event": "test"}'
        secret = "test_secret_key"
        # 10 minutes in future (beyond default 5 minute tolerance)
        future_timestamp = int(time.time()) + 600

        signature = generate_signature(payload, secret, future_timestamp)

        assert verify_signature(payload, secret, signature) is False

    def test_verify_signature_within_tolerance(self):
        """verify_signature should return True for timestamp within tolerance."""
        from semrush_core.webhooks.signature import generate_signature, verify_signature

        payload = '{"event": "test"}'
        secret = "test_secret_key"
        # 2 minutes ago (within default 5 minute tolerance)
        recent_timestamp = int(time.time()) - 120

        signature = generate_signature(payload, secret, recent_timestamp)

        assert verify_signature(payload, secret, signature) is True

    def test_verify_signature_custom_tolerance(self):
        """verify_signature should respect custom tolerance."""
        from semrush_core.webhooks.signature import generate_signature, verify_signature

        payload = '{"event": "test"}'
        secret = "test_secret_key"
        # 2 minutes ago
        timestamp = int(time.time()) - 120

        signature = generate_signature(payload, secret, timestamp)

        # Should fail with 60 second tolerance
        assert verify_signature(payload, secret, signature, tolerance=60) is False
        # Should pass with 300 second tolerance
        assert verify_signature(payload, secret, signature, tolerance=300) is True

    def test_verify_signature_malformed_header(self):
        """verify_signature should return False for malformed signature header."""
        from semrush_core.webhooks.signature import verify_signature

        payload = '{"event": "test"}'
        secret = "test_secret_key"

        # Missing v1
        assert verify_signature(payload, secret, "t=1234567890") is False
        # Missing t
        assert verify_signature(payload, secret, "v1=abcd1234") is False
        # Completely invalid
        assert verify_signature(payload, secret, "invalid") is False

    def test_verify_signature_empty_values(self):
        """verify_signature should handle empty values gracefully."""
        from semrush_core.webhooks.signature import verify_signature

        payload = '{"event": "test"}'
        secret = "test_secret_key"

        # Empty timestamp
        assert verify_signature(payload, secret, "t=,v1=abc") is False
        # Empty signature
        assert verify_signature(payload, secret, "t=1234567890,v1=") is False


# =============================================================================
# Webhook Delivery Retry Scheduling Tests
# =============================================================================


class TestWebhookRetryScheduling:
    """Tests for webhook delivery retry scheduling."""

    def test_schedule_retry_returns_datetime_for_first_attempt(self):
        """schedule_retry should return a datetime for first retry."""
        from semrush_core.webhooks.delivery import schedule_retry

        next_retry = schedule_retry(attempts=0)

        assert isinstance(next_retry, datetime)

    def test_schedule_retry_returns_none_when_max_retries_exceeded(self):
        """schedule_retry should return None when max retries exceeded."""
        from semrush_core.webhooks.delivery import MAX_RETRIES, schedule_retry

        next_retry = schedule_retry(attempts=MAX_RETRIES)

        assert next_retry is None

    def test_schedule_retry_delay_increases_with_attempts(self):
        """schedule_retry delays should increase with attempt count."""
        from semrush_core.webhooks.delivery import schedule_retry

        now = datetime.now(UTC)

        delays = []
        for attempts in range(5):
            next_retry = schedule_retry(attempts=attempts, base_time=now)
            if next_retry:
                delay = (next_retry - now).total_seconds()
                delays.append(delay)

        # Each delay should be >= previous (exponential backoff)
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1]

    def test_schedule_retry_uses_correct_delays(self):
        """schedule_retry should use the defined backoff delays."""
        from semrush_core.webhooks.delivery import RETRY_DELAYS, schedule_retry

        now = datetime.now(UTC)

        for attempt_num, expected_delay in enumerate(RETRY_DELAYS):
            next_retry = schedule_retry(attempts=attempt_num, base_time=now)
            actual_delay = (next_retry - now).total_seconds()
            assert actual_delay == expected_delay, (
                f"Attempt {attempt_num}: expected {expected_delay}s, got {actual_delay}s"
            )

    def test_schedule_retry_uses_last_delay_for_high_attempts(self):
        """schedule_retry should use last delay for attempts beyond RETRY_DELAYS length."""
        from semrush_core.webhooks.delivery import RETRY_DELAYS, schedule_retry

        now = datetime.now(UTC)

        # Attempt count just below MAX_RETRIES but beyond RETRY_DELAYS length
        high_attempt = len(RETRY_DELAYS)
        next_retry = schedule_retry(attempts=high_attempt, base_time=now)

        if next_retry:
            actual_delay = (next_retry - now).total_seconds()
            assert actual_delay == RETRY_DELAYS[-1]


class TestWebhookRetryConstants:
    """Tests for webhook retry constants."""

    def test_retry_delays_defined(self):
        """RETRY_DELAYS should be defined with expected values."""
        from semrush_core.webhooks.delivery import RETRY_DELAYS

        # Expected: 1m, 5m, 30m, 2h, 12h in seconds
        expected = [60, 300, 1800, 7200, 43200]
        assert expected == RETRY_DELAYS

    def test_max_retries_defined(self):
        """MAX_RETRIES should be defined as 5."""
        from semrush_core.webhooks.delivery import MAX_RETRIES

        assert MAX_RETRIES == 5


# =============================================================================
# Webhook Delivery Service Tests
# =============================================================================


class TestWebhookDeliveryService:
    """Tests for the webhook delivery service."""

    @pytest.mark.asyncio
    async def test_deliver_webhook_success(self):
        """deliver_webhook should return True and update status on success."""
        from semrush_core.webhooks.delivery import deliver_webhook

        # Create mock delivery
        delivery = MagicMock(spec=WebhookDelivery)
        delivery.id = uuid4()
        delivery.webhook_config_id = uuid4()
        delivery.event_type = "test.ping"
        delivery.payload = {"test": "data"}
        delivery.attempts = 0
        delivery.delivery_status = DeliveryStatus.PENDING.value

        # Create mock webhook config
        webhook_config = MagicMock(spec=WebhookConfig)
        webhook_config.url = "https://example.com/webhook"
        webhook_config.secret = "decrypted_secret"
        webhook_config.is_enabled = True

        # Mock the HTTP response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        with patch("semrush_core.webhooks.delivery.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await deliver_webhook(
                delivery=delivery,
                webhook_config=webhook_config,
            )

        assert result is True
        assert delivery.delivery_status == DeliveryStatus.SUCCESS.value
        assert delivery.response_status == 200
        assert delivery.attempts == 1

    @pytest.mark.asyncio
    async def test_deliver_webhook_failure_http_error(self):
        """deliver_webhook should return False and schedule retry on HTTP error."""
        from semrush_core.webhooks.delivery import deliver_webhook

        delivery = MagicMock(spec=WebhookDelivery)
        delivery.id = uuid4()
        delivery.webhook_config_id = uuid4()
        delivery.event_type = "test.ping"
        delivery.payload = {"test": "data"}
        delivery.attempts = 0
        delivery.delivery_status = DeliveryStatus.PENDING.value

        webhook_config = MagicMock(spec=WebhookConfig)
        webhook_config.url = "https://example.com/webhook"
        webhook_config.secret = "decrypted_secret"
        webhook_config.is_enabled = True

        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("semrush_core.webhooks.delivery.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await deliver_webhook(
                delivery=delivery,
                webhook_config=webhook_config,
            )

        assert result is False
        assert delivery.delivery_status == DeliveryStatus.PENDING.value
        assert delivery.response_status == 500
        assert delivery.attempts == 1
        assert delivery.next_retry_at is not None

    @pytest.mark.asyncio
    async def test_deliver_webhook_failure_connection_error(self):
        """deliver_webhook should handle connection errors gracefully."""
        import httpx
        from semrush_core.webhooks.delivery import deliver_webhook

        delivery = MagicMock(spec=WebhookDelivery)
        delivery.id = uuid4()
        delivery.webhook_config_id = uuid4()
        delivery.event_type = "test.ping"
        delivery.payload = {"test": "data"}
        delivery.attempts = 0
        delivery.delivery_status = DeliveryStatus.PENDING.value

        webhook_config = MagicMock(spec=WebhookConfig)
        webhook_config.url = "https://example.com/webhook"
        webhook_config.secret = "decrypted_secret"
        webhook_config.is_enabled = True

        with patch("semrush_core.webhooks.delivery.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.side_effect = httpx.ConnectError("Connection failed")
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await deliver_webhook(
                delivery=delivery,
                webhook_config=webhook_config,
            )

        assert result is False
        assert delivery.delivery_status == DeliveryStatus.PENDING.value
        assert delivery.attempts == 1
        assert delivery.next_retry_at is not None

    @pytest.mark.asyncio
    async def test_deliver_webhook_max_retries_exceeded(self):
        """deliver_webhook should mark as failed when max retries exceeded."""
        from semrush_core.webhooks.delivery import MAX_RETRIES, deliver_webhook

        delivery = MagicMock(spec=WebhookDelivery)
        delivery.id = uuid4()
        delivery.webhook_config_id = uuid4()
        delivery.event_type = "test.ping"
        delivery.payload = {"test": "data"}
        delivery.attempts = MAX_RETRIES  # Already at max
        delivery.delivery_status = DeliveryStatus.PENDING.value

        webhook_config = MagicMock(spec=WebhookConfig)
        webhook_config.url = "https://example.com/webhook"
        webhook_config.secret = "decrypted_secret"
        webhook_config.is_enabled = True

        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("semrush_core.webhooks.delivery.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await deliver_webhook(
                delivery=delivery,
                webhook_config=webhook_config,
            )

        assert result is False
        assert delivery.delivery_status == DeliveryStatus.FAILED.value
        assert delivery.next_retry_at is None

    @pytest.mark.asyncio
    async def test_deliver_webhook_includes_signature_header(self):
        """deliver_webhook should include signature in headers."""
        from semrush_core.webhooks.delivery import deliver_webhook

        delivery = MagicMock(spec=WebhookDelivery)
        delivery.id = uuid4()
        delivery.webhook_config_id = uuid4()
        delivery.event_type = "test.ping"
        delivery.payload = {"test": "data"}
        delivery.attempts = 0
        delivery.delivery_status = DeliveryStatus.PENDING.value

        webhook_config = MagicMock(spec=WebhookConfig)
        webhook_config.url = "https://example.com/webhook"
        webhook_config.secret = "decrypted_secret"
        webhook_config.is_enabled = True

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        with patch("semrush_core.webhooks.delivery.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            await deliver_webhook(
                delivery=delivery,
                webhook_config=webhook_config,
            )

            # Verify the call included the signature header
            call_kwargs = mock_client_instance.post.call_args.kwargs
            headers = call_kwargs.get("headers", {})
            assert "X-Webhook-Signature" in headers
            assert headers["X-Webhook-Signature"].startswith("t=")
            assert ",v1=" in headers["X-Webhook-Signature"]

    @pytest.mark.asyncio
    async def test_deliver_webhook_includes_correct_headers(self):
        """deliver_webhook should include standard webhook headers."""
        from semrush_core.webhooks.delivery import deliver_webhook

        delivery = MagicMock(spec=WebhookDelivery)
        delivery.id = uuid4()
        delivery.webhook_config_id = uuid4()
        delivery.event_type = "crawl.completed"
        delivery.payload = {"project_id": "123"}
        delivery.attempts = 0
        delivery.delivery_status = DeliveryStatus.PENDING.value

        webhook_config = MagicMock(spec=WebhookConfig)
        webhook_config.url = "https://example.com/webhook"
        webhook_config.secret = "decrypted_secret"
        webhook_config.is_enabled = True

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        with patch("semrush_core.webhooks.delivery.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            await deliver_webhook(
                delivery=delivery,
                webhook_config=webhook_config,
            )

            call_kwargs = mock_client_instance.post.call_args.kwargs
            headers = call_kwargs.get("headers", {})

            assert headers.get("Content-Type") == "application/json"
            assert headers.get("X-Webhook-Event") == "crawl.completed"
            assert "X-Webhook-Delivery-Id" in headers

    @pytest.mark.asyncio
    async def test_deliver_webhook_timeout(self):
        """deliver_webhook should handle timeout errors."""
        import httpx
        from semrush_core.webhooks.delivery import deliver_webhook

        delivery = MagicMock(spec=WebhookDelivery)
        delivery.id = uuid4()
        delivery.webhook_config_id = uuid4()
        delivery.event_type = "test.ping"
        delivery.payload = {"test": "data"}
        delivery.attempts = 0
        delivery.delivery_status = DeliveryStatus.PENDING.value

        webhook_config = MagicMock(spec=WebhookConfig)
        webhook_config.url = "https://example.com/webhook"
        webhook_config.secret = "decrypted_secret"
        webhook_config.is_enabled = True

        with patch("semrush_core.webhooks.delivery.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.side_effect = httpx.TimeoutException("Request timed out")
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await deliver_webhook(
                delivery=delivery,
                webhook_config=webhook_config,
            )

        assert result is False
        assert delivery.attempts == 1
        assert delivery.next_retry_at is not None


# =============================================================================
# Webhook Model Tests (existing models)
# =============================================================================


class TestWebhookDeliveryModel:
    """Tests for the WebhookDelivery model."""

    def test_webhook_delivery_has_required_fields(self):
        """WebhookDelivery should have all required fields."""
        webhook_id = uuid4()
        # Note: SQLAlchemy defaults are applied at insert time, not instantiation
        # So we explicitly set values here for testing
        delivery = WebhookDelivery(
            webhook_config_id=webhook_id,
            event_type="crawl.completed",
            payload={"project_id": "123"},
            delivery_status=DeliveryStatus.PENDING.value,
            attempts=0,
        )

        assert delivery.webhook_config_id == webhook_id
        assert delivery.event_type == "crawl.completed"
        assert delivery.payload == {"project_id": "123"}
        assert delivery.delivery_status == DeliveryStatus.PENDING.value
        assert delivery.attempts == 0

    def test_webhook_delivery_status_properties(self):
        """WebhookDelivery should have status helper properties."""
        delivery = WebhookDelivery(
            webhook_config_id=uuid4(),
            event_type="test.ping",
            payload={},
            delivery_status=DeliveryStatus.PENDING.value,
        )

        assert delivery.is_pending is True
        assert delivery.is_success is False
        assert delivery.is_failed is False

        delivery.delivery_status = DeliveryStatus.SUCCESS.value
        assert delivery.is_pending is False
        assert delivery.is_success is True

        delivery.delivery_status = DeliveryStatus.FAILED.value
        assert delivery.is_failed is True


class TestWebhookConfigModel:
    """Tests for the WebhookConfig model."""

    def test_webhook_config_should_deliver_when_enabled_and_subscribed(self):
        """should_deliver should return True when enabled and event type subscribed."""
        config = WebhookConfig(
            project_id=uuid4(),
            url="https://example.com/webhook",
            secret="encrypted_secret",
            enabled_events=["crawl.completed", "alert.fired"],
            is_enabled=True,
        )

        assert config.should_deliver("crawl.completed") is True
        assert config.should_deliver("alert.fired") is True
        assert config.should_deliver("crawl.requested") is False

    def test_webhook_config_should_not_deliver_when_disabled(self):
        """should_deliver should return False when webhook is disabled."""
        config = WebhookConfig(
            project_id=uuid4(),
            url="https://example.com/webhook",
            secret="encrypted_secret",
            enabled_events=["crawl.completed"],
            is_enabled=False,
        )

        assert config.should_deliver("crawl.completed") is False


class TestDeliveryStatusEnum:
    """Tests for the DeliveryStatus enum."""

    def test_delivery_status_values(self):
        """DeliveryStatus enum should have expected values."""
        assert DeliveryStatus.PENDING.value == "pending"
        assert DeliveryStatus.SUCCESS.value == "success"
        assert DeliveryStatus.FAILED.value == "failed"
