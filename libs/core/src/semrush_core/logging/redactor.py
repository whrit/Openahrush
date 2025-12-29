"""
Secret redaction utilities for log messages.

Provides pattern-based redaction of sensitive information including:
- JWT tokens
- Bearer/OAuth tokens
- Passwords in connection strings
- API keys and secrets
- Webhook secrets
- Database URLs with embedded credentials
"""

import re
from typing import Final

SECRET_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    (re.compile(r"eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*", re.IGNORECASE), "[REDACTED_JWT]"),
    (re.compile(r"Bearer\s+([A-Za-z0-9_\-\.]+)", re.IGNORECASE), "Bearer [REDACTED_BEARER]"),
    (re.compile(r"(password|pwd|passwd)\s*[=:]\s*([^\s&;,]+)", re.IGNORECASE), r"\1=[REDACTED_PASSWORD]"),
    (re.compile(r"(api[_-]?key)\s*[=:]\s*([^\s&;,]+)", re.IGNORECASE), r"\1=[REDACTED_API_KEY]"),
    (re.compile(r"((?:client_)?secret)\s*[=:]\s*([^\s&;,]+)", re.IGNORECASE), r"\1=[REDACTED_SECRET]"),
    (re.compile(r"(webhook_secret)\s*[=:]\s*([^\s&;,]+)", re.IGNORECASE), r"\1=[REDACTED_WEBHOOK_SECRET]"),
    (re.compile(r"((?:postgresql|postgres|mysql|redis|mongodb|amqp)(?:\+\w+)?://[^:]+):([^@]+)@", re.IGNORECASE), r"\1:[REDACTED_DB_PASSWORD]@"),
    (re.compile(r"(token)\s*[=:]\s*([A-Za-z0-9_\-\.]{20,})", re.IGNORECASE), r"\1=[REDACTED_TOKEN]"),
    (re.compile(r"(access_token)\s*[=:]\s*([^\s&;,]+)", re.IGNORECASE), r"\1=[REDACTED_ACCESS_TOKEN]"),
    (re.compile(r"(refresh_token)\s*[=:]\s*([^\s&;,]+)", re.IGNORECASE), r"\1=[REDACTED_REFRESH_TOKEN]"),
]


def redact_secrets(message: str) -> str:
    """Redact sensitive information from a log message."""
    if not message:
        return message
    result = message
    for pattern, replacement in SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result
