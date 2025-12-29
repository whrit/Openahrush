"""
Audit context management for request information.

Provides utilities for extracting and managing request context
(IP address, user agent, request ID) for audit logging.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AuditContext:
    """
    Request context for audit logging.

    Stores information about the request that triggered an auditable action.

    Attributes:
        ip_address: Client IP address (may come from X-Forwarded-For).
        user_agent: Client user agent string.
        request_id: Optional request ID for tracing.
    """

    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None

    @classmethod
    def from_request(cls, request: Any) -> AuditContext:
        """
        Extract audit context from a FastAPI/Starlette request.

        Handles proxy headers (X-Forwarded-For) for real client IP.

        Args:
            request: FastAPI/Starlette Request object.

        Returns:
            AuditContext with extracted information.
        """
        # Get IP address (prefer X-Forwarded-For for proxy setups)
        ip_address: str | None = None

        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            # Take the first IP (original client)
            ip_address = x_forwarded_for.split(",")[0].strip()
        elif request.client:
            ip_address = request.client.host

        # Get user agent
        user_agent = request.headers.get("user-agent")

        # Get request ID (if present)
        request_id = request.headers.get("x-request-id")

        return cls(
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
