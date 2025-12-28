"""
JS candidate selector for hybrid rendering.

Selects pages that need JavaScript rendering based on heuristics.
Applies heuristics in priority order:
1. Required selectors missing (highest priority)
2. Thin DOM / empty content
3. SPA shell detected
4. Client-side redirect detected

Respects max_rendered_pages budget and records which heuristic triggered selection.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from semrush_workers.crawl.heuristics import (
    needs_js_client_redirect,
    needs_js_missing_selectors,
    needs_js_spa_shell,
    needs_js_thin_dom,
)

if TYPE_CHECKING:
    pass


class PageProtocol(Protocol):
    """Protocol for crawl page objects."""

    id: uuid.UUID
    url: str
    was_rendered: bool
    text_length: int
    word_count: int
    scripts: list[str]


class SelectorSettingsProtocol(Protocol):
    """Protocol for selector settings objects."""

    max_rendered_pages: int
    min_text_chars: int
    min_word_count: int
    required_selectors: list[str]


@dataclass
class JsCandidateResult:
    """
    Result of JS candidate selection.

    Attributes:
        page_id: UUID of the page selected for rendering.
        url: URL of the page.
        trigger: Name of the heuristic that triggered selection.
    """

    page_id: uuid.UUID
    url: str
    trigger: str


@dataclass
class DefaultSelectorSettings:
    """Default settings for JS selector."""

    max_rendered_pages: int = 200
    min_text_chars: int = 200
    min_word_count: int = 50
    required_selectors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.required_selectors is None:
            self.required_selectors = []


class JsSelector:
    """
    Selects pages that need JavaScript rendering.

    Applies heuristics to identify pages that likely require JS rendering
    to extract meaningful content. Respects budget limits.
    """

    def __init__(self, settings: Any | None = None) -> None:
        """
        Initialize the JS selector.

        Args:
            settings: Settings object with max_rendered_pages, min_text_chars,
                     min_word_count, and required_selectors.
        """
        if settings is None:
            settings = DefaultSelectorSettings()

        self._settings = settings
        self.max_rendered_pages = getattr(settings, "max_rendered_pages", 200)

    def get_trigger_for_page(self, page: Any, html: str) -> str | None:
        """
        Determine which heuristic triggers JS rendering for a page.

        Checks heuristics in priority order:
        1. Required selectors missing (highest priority)
        2. Thin DOM / empty content
        3. SPA shell detected
        4. Client-side redirect detected

        Args:
            page: Page data object.
            html: Raw HTML string.

        Returns:
            Name of the triggering heuristic, or None if no trigger.
        """
        # Priority 1: Required selectors missing
        if needs_js_missing_selectors(html, self._settings):
            return "missing_selectors"

        # Priority 2: Thin DOM
        if needs_js_thin_dom(page, self._settings):
            return "thin_dom"

        # Priority 3: SPA shell
        if needs_js_spa_shell(page, html):
            return "spa_shell"

        # Priority 4: Client redirect
        if needs_js_client_redirect(html):
            return "client_redirect"

        return None

    def select_candidates(
        self,
        pages: list[Any],
        htmls: list[str],
    ) -> list[JsCandidateResult]:
        """
        Select pages that need JS rendering.

        Filters out already-rendered pages, applies heuristics, and
        respects the max_rendered_pages budget.

        Args:
            pages: List of page data objects.
            htmls: List of HTML strings (same order as pages).

        Returns:
            List of JsCandidateResult objects for pages needing rendering.
        """
        candidates: list[JsCandidateResult] = []

        for page, html in zip(pages, htmls, strict=False):
            # Skip already rendered pages
            if getattr(page, "was_rendered", False):
                continue

            # Check if page needs rendering
            trigger = self.get_trigger_for_page(page, html)
            if trigger is not None:
                candidates.append(
                    JsCandidateResult(
                        page_id=page.id,
                        url=page.url,
                        trigger=trigger,
                    )
                )

            # Check budget
            if len(candidates) >= self.max_rendered_pages:
                break

        return candidates

    async def select_from_crawl_run(
        self,
        crawl_run_id: uuid.UUID,
        db_session: Any,
        storage_client: Any,
    ) -> list[JsCandidateResult]:
        """
        Select JS rendering candidates from a crawl run.

        Queries crawl_pages with was_rendered=false, loads HTML from storage,
        and applies heuristics to select candidates.

        Args:
            crawl_run_id: UUID of the crawl run.
            db_session: Database session for queries.
            storage_client: Storage client for loading HTML.

        Returns:
            List of JsCandidateResult objects.
        """
        # This would be implemented with actual database queries
        # For now, this is a placeholder that shows the intended interface
        raise NotImplementedError("select_from_crawl_run requires database integration")


async def update_crawl_run_status(
    crawl_run_id: uuid.UUID,
    status: str,
    db_session: Any,
) -> None:
    """
    Update crawl run status.

    Args:
        crawl_run_id: UUID of the crawl run.
        status: New status value (e.g., 'selecting_js').
        db_session: Database session for the update.
    """
    # Placeholder for database update
    raise NotImplementedError("update_crawl_run_status requires database integration")
