"""
Cache key generation utilities.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_params(params: dict[str, Any]) -> str:
    """
    Generate MD5 hash of parameters.

    Sorts parameters to ensure consistent hashing regardless of insertion order.

    Args:
        params: Dictionary of parameters to hash.

    Returns:
        32-character hex MD5 hash.
    """
    # Filter out None values and sort by key
    filtered = {k: v for k, v in sorted(params.items()) if v is not None}
    # Create deterministic JSON string
    param_str = json.dumps(filtered, sort_keys=True)
    # Return MD5 hash
    return hashlib.md5(param_str.encode()).hexdigest()


def build_cache_key(
    endpoint: str,
    resource_id: str,
    params: dict[str, Any] | None = None,
) -> str:
    """
    Build a cache key from endpoint, resource ID, and optional parameters.

    Key format: endpoint:resource_id[:params_hash]

    Args:
        endpoint: API endpoint name (e.g., "issues", "settings").
        resource_id: Resource identifier (e.g., project ID).
        params: Optional query parameters to include in key.

    Returns:
        Cache key string.
    """
    key = f"{endpoint}:{resource_id}"

    if params:
        # Filter out None values
        filtered_params = {k: v for k, v in params.items() if v is not None}
        if filtered_params:
            params_hash = hash_params(filtered_params)
            key = f"{key}:{params_hash}"

    return key
