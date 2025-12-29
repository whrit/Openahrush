"""
Webhook delivery service with retry logic.

Provides:
- Async webhook delivery with HTTP client
- Exponential backoff retry scheduling
- Signature header generation
- Response tracking
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx

from semrush_core.models.webhook import DeliveryStatus
from semrush_core.webhooks.signature import generate_signature

if TYPE_CHECKING:
    from semrush_core.models.webhook import WebhookConfig, WebhookDelivery


# Retry delays in seconds: 1 minute, 5 minutes, 30 minutes, 2 hours, 12 hours
RETRY_DELAYS: list[int] = [60, 300, 1800, 7200, 43200]

# Maximum number of delivery attempts
MAX_RETRIES: int = 5

# Default timeout for webhook delivery (in seconds)
DEFAULT_TIMEOUT: float = 30.0


def schedule_retry(
    attempts: int,
    base_time: datetime | None = None,
) -> datetime | None:
    """
    Schedule next retry attempt with exponential backoff.

    Uses predefined delay intervals that increase with each attempt.
    Returns None if max retries have been exceeded.

    Args:
        attempts: Number of attempts already made (0-indexed).
        base_time: Base time for calculating next retry. Defaults to now.

    Returns:
        datetime for next retry, or None if max retries exceeded.

    Example:
        >>> schedule_retry(0)  # First retry: 1 minute from now
        datetime(...)
        >>> schedule_retry(5)  # Max retries exceeded
        None
    """
    if attempts >= MAX_RETRIES:
        return None

    if base_time is None:
        base_time = datetime.now(UTC)

    # Get delay for this attempt (cap at last delay for high attempts)
    delay_index = min(attempts, len(RETRY_DELAYS) - 1)
    delay_seconds = RETRY_DELAYS[delay_index]

    return base_time + timedelta(seconds=delay_seconds)


async def deliver_webhook(
    delivery: WebhookDelivery,
    webhook_config: WebhookConfig,
    timeout: float = DEFAULT_TIMEOUT,
) -> bool:
    """
    Attempt to deliver a webhook.

    Sends the webhook payload to the configured URL with:
    - HMAC-SHA256 signature header
    - Event type header
    - Delivery ID header
    - JSON content type

    On success: Updates delivery status to SUCCESS.
    On failure: Increments attempts, schedules retry (or marks FAILED if max retries).

    Args:
        delivery: The WebhookDelivery record to deliver.
        webhook_config: The WebhookConfig with URL and secret.
        timeout: Request timeout in seconds.

    Returns:
        True if delivered successfully, False otherwise.

    Note:
        This function modifies the delivery object in place but does not
        commit to the database. The caller is responsible for committing.
    """
    # Serialize payload
    payload_str = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True)

    # Generate signature
    signature = generate_signature(payload_str, webhook_config.secret)

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": delivery.event_type,
        "X-Webhook-Delivery-Id": str(delivery.id),
    }

    # Track the attempt
    now = datetime.now(UTC)
    delivery.attempts += 1
    delivery.last_attempt_at = now

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                webhook_config.url,
                content=payload_str,
                headers=headers,
            )

            # Store response info
            delivery.response_status = response.status_code
            # Truncate response body to prevent storing huge responses
            delivery.response_body = response.text[:4096] if response.text else None

            # Check for success (2xx status codes)
            if 200 <= response.status_code < 300:
                delivery.delivery_status = DeliveryStatus.SUCCESS.value
                delivery.next_retry_at = None
                return True
            else:
                # HTTP error - schedule retry or mark failed
                return _handle_failure(delivery)

    except httpx.TimeoutException:
        delivery.response_body = "Request timed out"
        return _handle_failure(delivery)

    except httpx.ConnectError as e:
        delivery.response_body = f"Connection error: {e}"
        return _handle_failure(delivery)

    except httpx.HTTPError as e:
        delivery.response_body = f"HTTP error: {e}"
        return _handle_failure(delivery)

    except Exception as e:
        delivery.response_body = f"Unexpected error: {e}"
        return _handle_failure(delivery)


def _handle_failure(delivery: WebhookDelivery) -> bool:
    """
    Handle delivery failure - schedule retry or mark as failed.

    Args:
        delivery: The WebhookDelivery record that failed.

    Returns:
        Always False (delivery failed).
    """
    next_retry = schedule_retry(delivery.attempts)

    if next_retry is None:
        # Max retries exceeded
        delivery.delivery_status = DeliveryStatus.FAILED.value
        delivery.next_retry_at = None
    else:
        # Schedule retry
        delivery.delivery_status = DeliveryStatus.PENDING.value
        delivery.next_retry_at = next_retry

    return False
