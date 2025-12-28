"""
JS rendering decision heuristics.

Provides functions to determine whether a page needs JavaScript rendering
based on various signals like thin DOM, SPA shell detection, missing
selectors, and client-side redirects.

All heuristics return a boolean indicating whether JS rendering is recommended.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    pass


class PageDataProtocol(Protocol):
    """Protocol for page data objects."""

    text_length: int
    word_count: int
    scripts: list[str]


class HeuristicsSettingsProtocol(Protocol):
    """Protocol for heuristics settings objects."""

    min_text_chars: int
    min_word_count: int
    required_selectors: list[str]


# SPA framework root element IDs
SPA_ROOT_IDS = {"root", "app", "__next", "__nuxt", "svelte"}

# SPA bundle filename patterns (webpack, vite, etc.)
SPA_BUNDLE_PATTERNS = [
    re.compile(r"app\.[a-f0-9]+\.js", re.IGNORECASE),
    re.compile(r"main\.[a-f0-9]+\.js", re.IGNORECASE),
    re.compile(r"chunk\.", re.IGNORECASE),
]

# Client-side redirect patterns
REDIRECT_PATTERNS = [
    re.compile(r"window\.location\s*=", re.IGNORECASE),
    re.compile(r"window\.location\.href\s*=", re.IGNORECASE),
    re.compile(r"window\.location\.replace\s*\(", re.IGNORECASE),
    re.compile(r"document\.location\s*=", re.IGNORECASE),
    re.compile(r"document\.location\.href\s*=", re.IGNORECASE),
]

# Meta refresh pattern with capture group for delay
META_REFRESH_PATTERN = re.compile(
    r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\']?(\d+)',
    re.IGNORECASE,
)

# Maximum delay (in seconds) for meta refresh to be considered a redirect
MAX_META_REFRESH_DELAY = 5


def needs_js_thin_dom(page: Any, settings: Any) -> bool:
    """
    Detect pages with thin/empty DOM that likely need JS rendering.

    Returns True if:
    - text_length < min_text_chars (default 200)
    - word_count < min_word_count (default 50)

    Args:
        page: Page data object with text_length and word_count attributes.
        settings: Settings object with min_text_chars and min_word_count.

    Returns:
        True if the page appears to have thin DOM content.
    """
    min_text_chars = getattr(settings, "min_text_chars", 200)
    min_word_count = getattr(settings, "min_word_count", 50)

    text_length = getattr(page, "text_length", 0)
    word_count = getattr(page, "word_count", 0)

    return text_length < min_text_chars or word_count < min_word_count


def needs_js_spa_shell(page: Any, html: str) -> bool:
    """
    Detect SPA framework shells that need JS rendering.

    Checks for:
    - Single root element with SPA framework ID (#root, #app, #__next, etc.)
    - SPA bundle patterns in script sources (app.*.js, main.*.js, chunk.*.js)

    Args:
        page: Page data object with scripts attribute.
        html: Raw HTML string to analyze.

    Returns:
        True if the page appears to be an SPA shell.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Fallback to regex-based detection if BeautifulSoup not available
        return _detect_spa_shell_regex(page, html)

    soup = BeautifulSoup(html, "html.parser")
    body = soup.body

    if body:
        # Get direct children that are elements (not text/comments)
        # BeautifulSoup children can be Tag or NavigableString; filter to tags
        direct_children = [
            child
            for child in body.children
            if hasattr(child, "name") and child.name  # type: ignore[union-attr]
        ]

        # Check for single root element with SPA ID
        if len(direct_children) == 1:
            child = direct_children[0]
            element_id = child.get("id", "") if hasattr(child, "get") else ""
            if element_id in SPA_ROOT_IDS:
                # Check if the element is empty or has minimal content
                child_text = child.get_text(strip=True) if hasattr(child, "get_text") else ""
                # Also check if there are no meaningful child elements
                meaningful_children = [
                    c
                    for c in getattr(child, "children", [])
                    if hasattr(c, "name") and getattr(c, "name", None)
                ]
                if len(child_text) < 50 and len(meaningful_children) == 0:
                    return True

    # Check for SPA bundle patterns in scripts
    scripts = getattr(page, "scripts", []) or []
    for script in scripts:
        for pattern in SPA_BUNDLE_PATTERNS:
            if pattern.search(script):
                return True

    return False


def _detect_spa_shell_regex(page: Any, html: str) -> bool:
    """
    Fallback regex-based SPA shell detection.

    Used when BeautifulSoup is not available.

    Args:
        page: Page data object with scripts attribute.
        html: Raw HTML string to analyze.

    Returns:
        True if the page appears to be an SPA shell.
    """
    # Check for empty root divs
    for root_id in SPA_ROOT_IDS:
        pattern = re.compile(
            rf'<div[^>]+id=["\']?{root_id}["\']?[^>]*>\s*</div>',
            re.IGNORECASE,
        )
        if pattern.search(html):
            return True

    # Check for SPA bundle patterns in scripts
    scripts = getattr(page, "scripts", []) or []
    for script in scripts:
        for pattern in SPA_BUNDLE_PATTERNS:
            if pattern.search(script):
                return True

    return False


def needs_js_missing_selectors(html: str, settings: Any) -> bool:
    """
    Check if user-specified required selectors are missing from HTML.

    Reads required_selectors from project settings and returns True
    if any selector is not found in the HTML.

    Args:
        html: Raw HTML string to analyze.
        settings: Settings object with required_selectors list.

    Returns:
        True if any required selector is missing.
    """
    required_selectors = getattr(settings, "required_selectors", []) or []

    if not required_selectors:
        return False

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Cannot check selectors without BeautifulSoup
        return False

    soup = BeautifulSoup(html, "html.parser")

    return any(not soup.select_one(selector) for selector in required_selectors)


def needs_js_client_redirect(html: str) -> bool:
    """
    Detect client-side redirects in HTML.

    Checks for:
    - window.location assignments
    - window.location.href assignments
    - window.location.replace() calls
    - document.location assignments
    - meta refresh tags with low delay (<= 5 seconds)

    Args:
        html: Raw HTML string to analyze.

    Returns:
        True if client-side redirect patterns are detected.
    """
    # Check for JavaScript redirect patterns
    for pattern in REDIRECT_PATTERNS:
        if pattern.search(html):
            return True

    # Check for meta refresh with low delay
    match = META_REFRESH_PATTERN.search(html)
    if match:
        try:
            delay = int(match.group(1))
            if delay <= MAX_META_REFRESH_DELAY:
                return True
        except (ValueError, IndexError):
            # If we can't parse the delay, assume it's a redirect
            return True

    return False


def get_js_render_trigger(page: Any, html: str, settings: Any) -> str | None:
    """
    Determine which heuristic triggers JS rendering (if any).

    Checks heuristics in priority order:
    1. Required selectors missing (highest priority)
    2. Thin DOM / empty content
    3. SPA shell detected
    4. Client-side redirect detected

    Args:
        page: Page data object.
        html: Raw HTML string.
        settings: Settings object.

    Returns:
        Name of the triggering heuristic, or None if no trigger.
    """
    # Priority 1: Required selectors missing
    if needs_js_missing_selectors(html, settings):
        return "missing_selectors"

    # Priority 2: Thin DOM
    if needs_js_thin_dom(page, settings):
        return "thin_dom"

    # Priority 3: SPA shell
    if needs_js_spa_shell(page, html):
        return "spa_shell"

    # Priority 4: Client redirect
    if needs_js_client_redirect(html):
        return "client_redirect"

    return None


def should_render_js(page: Any, html: str, settings: Any) -> bool:
    """
    Determine if a page should be rendered with JavaScript.

    Convenience function that returns True if any heuristic triggers.

    Args:
        page: Page data object.
        html: Raw HTML string.
        settings: Settings object.

    Returns:
        True if JS rendering is recommended.
    """
    return get_js_render_trigger(page, html, settings) is not None
