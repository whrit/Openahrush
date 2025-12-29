"""
FastAPI rate limiting middleware.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from semrush_core.rate_limit.backend import RateLimitBackend, build_rate_limit_key
from semrush_core.rate_limit.config import RateLimitSettings, get_category_for_path

if TYPE_CHECKING:
    from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Applies configurable rate limits based on endpoint category.
    Returns 429 Too Many Requests when limit exceeded.
    Adds X-RateLimit-* headers to all responses.
    """

    def __init__(
        self,
        app: ASGIApp,
        backend: RateLimitBackend,
        settings: RateLimitSettings | None = None,
    ) -> None:
        """
        Initialize the rate limiting middleware.

        Args:
            app: The ASGI application.
            backend: Rate limit backend for Redis operations.
            settings: Rate limit configuration. Uses defaults if not provided.
        """
        super().__init__(app)
        self._backend = backend
        self._settings = settings or RateLimitSettings()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Response:
        """
        Process a request with rate limiting.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler in the chain.

        Returns:
            Response with rate limit headers.
        """
        path = request.url.path
        method = request.method

        # Get category for this endpoint
        category = get_category_for_path(path, method)

        # Skip rate limiting for uncategorized endpoints
        if category is None:
            return await call_next(request)

        # Get identifier: user ID if authenticated, IP otherwise
        identifier = self._get_identifier(request)

        # Get limits for this category
        limit, window = self._settings.get_limit_for_category(category)

        # Build rate limit key
        key = build_rate_limit_key(category, identifier)

        try:
            allowed, remaining, reset_at = await self._backend.is_allowed(
                key=key,
                limit=limit,
                window_seconds=window,
            )
        except Exception as e:
            logger.error("Rate limit backend error: %s", e)
            # Fail open
            return await call_next(request)

        # Build rate limit headers
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_at),
        }

        if not allowed:
            # Rate limited
            headers["Retry-After"] = str(window)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too Many Requests",
                    "retry_after": window,
                },
                headers=headers,
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value

        return response

    def _get_identifier(self, request: Request) -> str:
        """
        Get the identifier for rate limiting.

        Uses user ID if authenticated, otherwise falls back to IP address.

        Args:
            request: The incoming request.

        Returns:
            Identifier string.
        """
        # Try to get user ID from request state (set by auth middleware)
        try:
            if hasattr(request.state, "user") and request.state.user is not None:
                return str(request.state.user.id)
        except Exception:
            pass

        # Fall back to IP address
        if request.client is not None:
            return request.client.host

        # Last resort: use a placeholder
        return "unknown"
