"""
Caching decorators for API endpoints.
"""

from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import Request, Response

from semrush_core.cache.headers import build_cache_control
from semrush_core.cache.keys import build_cache_key

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def cached(
    backend: Any,
    ttl: int,
    key_builder: Callable[..., str] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to cache endpoint responses.

    Caches the response in Redis with the specified TTL.
    Respects Cache-Control: no-cache header to bypass cache.
    Adds Cache-Control header to response when Response parameter is present.

    Args:
        backend: CacheBackend instance.
        ttl: Time-to-live in seconds.
        key_builder: Optional custom key builder function.

    Returns:
        Decorated function.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find Request in args or kwargs
            request: Request | None = None
            response: Response | None = None

            # Check args
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif isinstance(arg, Response):
                    response = arg

            # Check kwargs
            for value in kwargs.values():
                if isinstance(value, Request):
                    request = value
                elif isinstance(value, Response):
                    response = value

            # Check for no-cache header
            if request is not None:
                cache_control = request.headers.get("cache-control", "")
                if "no-cache" in cache_control.lower():
                    # Bypass cache, call function directly
                    result = await func(*args, **kwargs)
                    if response is not None:
                        response.headers["Cache-Control"] = build_cache_control(
                            max_age=ttl, private=True
                        )
                    return result

            # Build cache key
            if key_builder is not None:
                cache_key = key_builder(request, **kwargs)
            else:
                # Default key builder - find resource ID parameter
                resource_id = "default"
                for param_name in ["project_id", "crawl_run_id", "id"]:
                    if param_name in kwargs:
                        resource_id = str(kwargs[param_name])
                        break

                # Get query params from request
                query_params = {}
                if request is not None and hasattr(request, "query_params"):
                    query_params = dict(request.query_params)

                cache_key = build_cache_key(
                    endpoint=func.__name__,
                    resource_id=resource_id,
                    params=query_params,
                )

            # Try to get from cache
            try:
                cached_value = await backend.get(cache_key)
                if cached_value is not None:
                    logger.debug("Cache hit for key: %s", cache_key)
                    if response is not None:
                        response.headers["Cache-Control"] = build_cache_control(
                            max_age=ttl, private=True
                        )
                    return cached_value
            except Exception as e:
                logger.warning("Cache get error: %s", e)

            # Cache miss - call function
            result = await func(*args, **kwargs)

            # Store in cache
            try:
                # Convert result to dict if it has model_dump (Pydantic model)
                cache_value = result
                if hasattr(result, "model_dump"):
                    cache_value = result.model_dump()
                elif hasattr(result, "dict"):
                    cache_value = result.dict()

                await backend.set(cache_key, cache_value, ttl=ttl)
                logger.debug("Cached key: %s with TTL: %d", cache_key, ttl)
            except Exception as e:
                logger.warning("Cache set error: %s", e)

            # Add Cache-Control header
            if response is not None:
                response.headers["Cache-Control"] = build_cache_control(max_age=ttl, private=True)

            return result

        return wrapper  # type: ignore[return-value]

    return decorator


def invalidate_cache(
    backend: Any,
    pattern: str | list[str],
) -> Callable[[F], F]:
    """
    Decorator to invalidate cache after a mutation.

    Deletes all cache keys matching the pattern(s) after the function executes.
    Does not invalidate if the function raises an exception.

    Pattern variables in curly braces are replaced with function argument values.
    Example: "issues:{project_id}:*" with project_id="123" becomes "issues:123:*"

    Args:
        backend: CacheBackend instance.
        pattern: Pattern or list of patterns to invalidate.

    Returns:
        Decorated function.
    """
    patterns = [pattern] if isinstance(pattern, str) else pattern

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Call the function first
            result = await func(*args, **kwargs)

            # Get function signature to map args to parameter names
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Invalidate cache patterns
            for pat in patterns:
                # Replace placeholders with actual values
                resolved_pattern = pat
                for param_name, param_value in bound.arguments.items():
                    placeholder = "{" + param_name + "}"
                    if placeholder in resolved_pattern:
                        resolved_pattern = resolved_pattern.replace(placeholder, str(param_value))

                try:
                    deleted = await backend.delete_pattern(resolved_pattern)
                    logger.debug(
                        "Invalidated %d keys matching pattern: %s",
                        deleted,
                        resolved_pattern,
                    )
                except Exception as e:
                    logger.warning("Cache invalidation error: %s", e)

            return result

        return wrapper  # type: ignore[return-value]

    return decorator
