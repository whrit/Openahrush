"""
Cache-Control header utilities.
"""

from __future__ import annotations

# Cache-Control directive constants
CACHE_CONTROL_PRIVATE = "private"
CACHE_CONTROL_PUBLIC = "public"
CACHE_CONTROL_NO_STORE = "no-store"


def build_cache_control(
    max_age: int | None = None,
    private: bool = True,
    no_store: bool = False,
    must_revalidate: bool = False,
) -> str:
    """
    Build a Cache-Control header value.

    Args:
        max_age: Maximum age in seconds.
        private: If True, use private; if False, use public.
        no_store: If True, return "no-store" only.
        must_revalidate: If True, add must-revalidate directive.

    Returns:
        Cache-Control header value string.
    """
    if no_store:
        return "no-store"

    directives = []

    # Add visibility directive
    if private:
        directives.append("private")
    else:
        directives.append("public")

    # Add max-age if provided
    if max_age is not None:
        directives.append(f"max-age={max_age}")

    # Add must-revalidate if requested
    if must_revalidate:
        directives.append("must-revalidate")

    return ", ".join(directives)
