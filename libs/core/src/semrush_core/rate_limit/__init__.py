"""
API Rate Limiting module for the Openahrush API.

Provides Redis-backed rate limiting with:
- Sliding window algorithm for accurate rate tracking
- Configurable limits per endpoint category
- X-RateLimit-* headers in responses
- 429 Too Many Requests when exceeded

Endpoint Categories and Default Limits:
- AUTH: 5/minute (login, register)
- CRAWL_TRIGGER: 10/hour
- EXPORT_TRIGGER: 20/hour
- API_READ: 100/minute
- WEBHOOK_CONFIG: 10/minute
"""

from semrush_core.rate_limit.backend import RateLimitBackend, build_rate_limit_key
from semrush_core.rate_limit.config import (
    ENDPOINT_CATEGORY_MAPPINGS,
    EndpointCategory,
    RateLimitSettings,
    get_category_for_path,
)
from semrush_core.rate_limit.middleware import RateLimitMiddleware

__all__ = [
    "RateLimitBackend",
    "RateLimitMiddleware",
    "RateLimitSettings",
    "EndpointCategory",
    "ENDPOINT_CATEGORY_MAPPINGS",
    "get_category_for_path",
    "build_rate_limit_key",
]
