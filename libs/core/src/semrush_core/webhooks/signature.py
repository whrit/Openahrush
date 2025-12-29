"""
Webhook signature generation and verification.

Implements HMAC-SHA256 signing with timestamp-based replay protection.

The signature format is: t=<timestamp>,v1=<signature>
where:
- timestamp: Unix epoch seconds when the signature was created
- signature: HMAC-SHA256 of "{timestamp}.{payload}" using the webhook secret

This follows the same pattern used by Stripe, GitHub, and other webhook providers.
"""

import hashlib
import hmac
import time


def generate_signature(payload: str, secret: str, timestamp: int | None = None) -> str:
    """
    Generate HMAC-SHA256 signature for webhook payload.

    The signature includes a timestamp for replay protection. The receiving
    endpoint should verify that the timestamp is recent (within tolerance).

    Args:
        payload: The JSON payload string to sign.
        secret: The webhook secret key (plaintext).
        timestamp: Unix epoch timestamp. If None, uses current time.

    Returns:
        Signature string in format: t=<timestamp>,v1=<hex_signature>

    Example:
        >>> generate_signature('{"event": "test"}', 'secret123', 1234567890)
        't=1234567890,v1=a1b2c3...'
    """
    if timestamp is None:
        timestamp = int(time.time())

    # Create the signed message: timestamp.payload
    message = f"{timestamp}.{payload}"

    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"t={timestamp},v1={signature}"


def verify_signature(
    payload: str,
    secret: str,
    signature_header: str,
    tolerance: int = 300,
) -> bool:
    """
    Verify webhook signature is valid and not expired.

    Performs the following checks:
    1. Parses the signature header to extract timestamp and signature
    2. Verifies the timestamp is within the tolerance window
    3. Computes the expected signature and compares (timing-safe)

    Args:
        payload: The JSON payload string that was signed.
        secret: The webhook secret key (plaintext).
        signature_header: The signature header value (t=...,v1=...).
        tolerance: Maximum age in seconds for the timestamp (default: 300 = 5 minutes).

    Returns:
        True if signature is valid and timestamp is within tolerance, False otherwise.

    Example:
        >>> verify_signature('{"event": "test"}', 'secret123', 't=1234567890,v1=abc...')
        True
    """
    try:
        # Parse signature header
        # Expected format: t=<timestamp>,v1=<signature>
        parts_dict: dict[str, str] = {}
        for part in signature_header.split(","):
            if "=" in part:
                key, value = part.split("=", 1)
                parts_dict[key] = value

        timestamp_str = parts_dict.get("t", "")
        expected_sig = parts_dict.get("v1", "")

        # Validate we have both required parts
        if not timestamp_str or not expected_sig:
            return False

        # Parse timestamp
        timestamp = int(timestamp_str)

        # Check timestamp is within tolerance
        current_time = int(time.time())
        if abs(current_time - timestamp) > tolerance:
            return False

        # Compute expected signature
        message = f"{timestamp}.{payload}"
        computed_sig = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Timing-safe comparison
        return hmac.compare_digest(computed_sig, expected_sig)

    except (ValueError, KeyError, TypeError):
        # Any parsing error means invalid signature
        return False
