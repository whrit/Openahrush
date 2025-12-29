"""
Webhook delivery service with HMAC-SHA256 signing and exponential backoff retries.

Provides:
- compute_signature: Generate HMAC-SHA256 signature for webhook payload
- WebhookDeliveryService: Service for delivering webhooks to configured endpoints

Delivery semantics:
- At-least-once delivery with retries
- Exponential backoff: 1min, 5min, 30min, 2hr, 24hr
- HMAC-SHA256 signature in X-Webhook-Signature header
- Delivery tracking with status updates
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
from semrush_core.models import DeliveryStatus, WebhookConfig, WebhookDelivery
from semrush_core.security.encryption import decrypt_token
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Retry schedule in minutes: 1min, 5min, 30min, 2hr, 24hr
RETRY_DELAYS_MINUTES = [1, 5, 30, 120, 1440]
MAX_ATTEMPTS = len(RETRY_DELAYS_MINUTES) + 1  # Initial attempt + retries

# HTTP timeout for webhook delivery
DELIVERY_TIMEOUT_SECONDS = 30

# Maximum response body size to store (bytes)
MAX_RESPONSE_BODY_SIZE = 4096


def compute_signature(payload: str, secret: str) -> str:
    """
    Compute HMAC-SHA256 signature for a webhook payload.

    Args:
        payload: The JSON payload as a string.
        secret: The webhook secret (plaintext).

    Returns:
        Hex-encoded HMAC-SHA256 signature.

    Example:
        >>> payload = '{"event_type": "crawl.completed"}'
        >>> secret = "my-webhook-secret"
        >>> sig = compute_signature(payload, secret)
        >>> len(sig) == 64  # 32 bytes as hex
        True
    """
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=payload.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def get_next_retry_delay(attempt: int) -> timedelta | None:
    """
    Get the delay until the next retry attempt.

    Args:
        attempt: The current attempt number (1-indexed).

    Returns:
        Timedelta for the next retry, or None if max retries exceeded.
    """
    retry_index = attempt - 1  # Convert to 0-indexed for retry schedule
    if retry_index >= len(RETRY_DELAYS_MINUTES):
        return None

    return timedelta(minutes=RETRY_DELAYS_MINUTES[retry_index])


class WebhookDeliveryService:
    """
    Service for delivering webhooks with retries and signature verification.

    Handles:
    - Async HTTP delivery with httpx
    - HMAC-SHA256 signature generation
    - Exponential backoff retries
    - Delivery status tracking

    Attributes:
        db: Database session.
        http_client: Optional httpx client (created if not provided).
    """

    def __init__(
        self,
        db: AsyncSession,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize the delivery service.

        Args:
            db: Database session.
            http_client: Optional httpx client for testing.
        """
        self._db = db
        self._http_client = http_client
        self._owns_client = http_client is None

    async def __aenter__(self) -> WebhookDeliveryService:
        """Context manager entry."""
        if self._owns_client:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(DELIVERY_TIMEOUT_SECONDS),
                follow_redirects=True,
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        if self._owns_client and self._http_client:
            await self._http_client.aclose()

    async def deliver_event(
        self,
        project_id: uuid.UUID,
        event_type: str,
        event_payload: dict[str, Any],
    ) -> list[uuid.UUID]:
        """
        Deliver an event to all subscribed webhooks for a project.

        Creates delivery records for each webhook and attempts immediate
        delivery. Failed deliveries will be retried by the worker.

        Args:
            project_id: Project UUID.
            event_type: The event type (e.g., "crawl.completed").
            event_payload: The event payload (will be wrapped in envelope).

        Returns:
            List of created delivery UUIDs.
        """
        # Find all enabled webhooks for this project that subscribe to this event
        result = await self._db.execute(
            select(WebhookConfig).where(
                WebhookConfig.project_id == project_id,
                WebhookConfig.is_enabled == True,  # noqa: E712
            )
        )
        webhooks = result.scalars().all()

        delivery_ids: list[uuid.UUID] = []

        for webhook in webhooks:
            if not webhook.should_deliver(event_type):
                continue

            # Create event envelope
            now = datetime.now(UTC)
            delivery_id = uuid.uuid4()
            envelope = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "occurred_at": now.isoformat(),
                "project_id": str(project_id),
                "delivery_id": str(delivery_id),
                "payload": event_payload,
            }

            # Create delivery record
            delivery = WebhookDelivery(
                id=delivery_id,
                webhook_config_id=webhook.id,
                event_type=event_type,
                payload=envelope,
                delivery_status=DeliveryStatus.PENDING.value,
            )

            self._db.add(delivery)
            delivery_ids.append(delivery_id)

        await self._db.commit()

        # Attempt immediate delivery for each
        for delivery_id in delivery_ids:
            await self.attempt_delivery(delivery_id)

        return delivery_ids

    async def attempt_delivery(
        self,
        delivery_id: uuid.UUID,
    ) -> bool:
        """
        Attempt to deliver a pending webhook.

        Args:
            delivery_id: Delivery record UUID.

        Returns:
            True if delivery succeeded, False otherwise.
        """
        # Get delivery record
        result = await self._db.execute(
            select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
        )
        delivery = result.scalar_one_or_none()

        if delivery is None:
            logger.warning("Delivery record not found: %s", delivery_id)
            return False

        if delivery.delivery_status != DeliveryStatus.PENDING.value:
            logger.debug("Delivery %s is not pending, skipping", delivery_id)
            return delivery.delivery_status == DeliveryStatus.SUCCESS.value

        # Get webhook config
        result = await self._db.execute(
            select(WebhookConfig).where(WebhookConfig.id == delivery.webhook_config_id)
        )
        webhook = result.scalar_one_or_none()

        if webhook is None:
            logger.warning("Webhook config not found for delivery: %s", delivery_id)
            delivery.delivery_status = DeliveryStatus.FAILED.value
            await self._db.commit()
            return False

        if not webhook.is_enabled:
            logger.info("Webhook %s is disabled, marking delivery as failed", webhook.id)
            delivery.delivery_status = DeliveryStatus.FAILED.value
            await self._db.commit()
            return False

        # Attempt delivery
        delivery.attempts += 1
        delivery.last_attempt_at = datetime.now(UTC)

        try:
            success = await self._send_webhook(
                url=webhook.url,
                encrypted_secret=webhook.secret,
                payload=delivery.payload,
                delivery=delivery,
            )

            if success:
                delivery.delivery_status = DeliveryStatus.SUCCESS.value
                delivery.next_retry_at = None
                logger.info(
                    "Webhook delivery succeeded: %s to %s",
                    delivery_id,
                    webhook.url,
                )
            else:
                # Schedule retry or mark as failed
                retry_delay = get_next_retry_delay(delivery.attempts)
                if retry_delay:
                    delivery.next_retry_at = datetime.now(UTC) + retry_delay
                    logger.info(
                        "Webhook delivery failed, retry scheduled in %s: %s",
                        retry_delay,
                        delivery_id,
                    )
                else:
                    delivery.delivery_status = DeliveryStatus.FAILED.value
                    delivery.next_retry_at = None
                    logger.warning(
                        "Webhook delivery failed permanently after %d attempts: %s",
                        delivery.attempts,
                        delivery_id,
                    )

            await self._db.commit()
            return success

        except Exception as e:
            logger.exception("Unexpected error during webhook delivery: %s", e)
            # Schedule retry on unexpected errors
            retry_delay = get_next_retry_delay(delivery.attempts)
            if retry_delay:
                delivery.next_retry_at = datetime.now(UTC) + retry_delay
            else:
                delivery.delivery_status = DeliveryStatus.FAILED.value
                delivery.next_retry_at = None

            delivery.response_body = f"Internal error: {e!s}"[:MAX_RESPONSE_BODY_SIZE]
            await self._db.commit()
            return False

    async def _send_webhook(
        self,
        url: str,
        encrypted_secret: str,
        payload: dict[str, Any],
        delivery: WebhookDelivery,
    ) -> bool:
        """
        Send the webhook HTTP request.

        Args:
            url: Webhook endpoint URL.
            encrypted_secret: Encrypted webhook secret.
            payload: Event payload.
            delivery: Delivery record for status updates.

        Returns:
            True if delivery succeeded (2xx response), False otherwise.
        """
        if self._http_client is None:
            raise RuntimeError("HTTP client not initialized. Use async context manager.")

        # Serialize payload
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        # Decrypt secret and compute signature
        try:
            secret = decrypt_token(encrypted_secret)
        except Exception as e:
            logger.error("Failed to decrypt webhook secret: %s", e)
            delivery.response_body = "Failed to decrypt webhook secret"
            return False

        signature = compute_signature(payload_json, secret)

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Delivery-Id": str(delivery.id),
            "User-Agent": "Openahrush-Webhook/1.0",
        }

        try:
            response = await self._http_client.post(
                url,
                content=payload_json,
                headers=headers,
            )

            delivery.response_status = response.status_code
            delivery.response_body = response.text[:MAX_RESPONSE_BODY_SIZE]

            # Success if 2xx response
            return 200 <= response.status_code < 300

        except httpx.TimeoutException:
            delivery.response_body = f"Request timeout after {DELIVERY_TIMEOUT_SECONDS}s"
            logger.warning("Webhook delivery timed out: %s", url)
            return False

        except httpx.ConnectError as e:
            delivery.response_body = f"Connection error: {e!s}"[:MAX_RESPONSE_BODY_SIZE]
            logger.warning("Webhook connection error: %s - %s", url, e)
            return False

        except httpx.RequestError as e:
            delivery.response_body = f"Request error: {e!s}"[:MAX_RESPONSE_BODY_SIZE]
            logger.warning("Webhook request error: %s - %s", url, e)
            return False

    async def process_pending_deliveries(
        self,
        batch_size: int = 100,
    ) -> int:
        """
        Process pending deliveries that are due for retry.

        This method should be called periodically by a worker.

        Args:
            batch_size: Maximum number of deliveries to process.

        Returns:
            Number of deliveries processed.
        """
        now = datetime.now(UTC)

        # Find pending deliveries that are due for retry
        result = await self._db.execute(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.delivery_status == DeliveryStatus.PENDING.value,
                (WebhookDelivery.next_retry_at <= now) | (WebhookDelivery.next_retry_at.is_(None)),
            )
            .limit(batch_size)
        )
        deliveries = result.scalars().all()

        processed = 0
        for delivery in deliveries:
            await self.attempt_delivery(delivery.id)
            processed += 1

        return processed

    async def get_delivery_stats(
        self,
        webhook_config_id: uuid.UUID,
    ) -> dict[str, int]:
        """
        Get delivery statistics for a webhook.

        Args:
            webhook_config_id: Webhook config UUID.

        Returns:
            Dictionary with counts by status.
        """
        from sqlalchemy import func

        stats: dict[str, int] = {}

        for status_value in DeliveryStatus:
            result = await self._db.execute(
                select(func.count(WebhookDelivery.id)).where(
                    WebhookDelivery.webhook_config_id == webhook_config_id,
                    WebhookDelivery.delivery_status == status_value.value,
                )
            )
            stats[status_value.value] = result.scalar() or 0

        return stats
