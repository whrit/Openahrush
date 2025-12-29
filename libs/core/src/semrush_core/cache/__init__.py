"""
Response caching module for the Openahrush API.

Provides Redis-backed response caching with:
- CacheBackend: Async Redis cache operations
- @cached decorator: Cache endpoint responses with TTL
- @invalidate_cache decorator: Invalidate cache on mutations
- Cache key generation with params hashing
- Cache-Control header utilities

TTL Constants (in seconds):
- TTL_ISSUES: 300 (5 minutes)
- TTL_REFDOMAINS: 3600 (1 hour)
- TTL_SNAPSHOTS: 3600 (1 hour)
- TTL_SETTINGS: 600 (10 minutes)
"""

from semrush_core.cache.backend import CacheBackend
from semrush_core.cache.decorator import cached, invalidate_cache
from semrush_core.cache.headers import (
    CACHE_CONTROL_NO_STORE,
    CACHE_CONTROL_PRIVATE,
    CACHE_CONTROL_PUBLIC,
    build_cache_control,
)
from semrush_core.cache.keys import build_cache_key, hash_params

# TTL constants for different endpoint types (in seconds)
TTL_ISSUES = 300  # 5 minutes
TTL_REFDOMAINS = 3600  # 1 hour
TTL_SNAPSHOTS = 3600  # 1 hour
TTL_SETTINGS = 600  # 10 minutes

__all__ = [
    "CacheBackend",
    "cached",
    "invalidate_cache",
    "build_cache_key",
    "hash_params",
    "build_cache_control",
    "CACHE_CONTROL_PRIVATE",
    "CACHE_CONTROL_PUBLIC",
    "CACHE_CONTROL_NO_STORE",
    "TTL_ISSUES",
    "TTL_REFDOMAINS",
    "TTL_SNAPSHOTS",
    "TTL_SETTINGS",
]
