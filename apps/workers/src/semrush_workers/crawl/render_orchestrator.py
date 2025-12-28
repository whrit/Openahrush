"""
Render orchestrator for hybrid JS rendering.

Orchestrates the complete JS rendering flow:
1. Select candidates based on heuristics
2. Render pages with Playwright
3. Re-extract page data from rendered HTML
4. Store rendered HTML to MinIO
5. Update crawl_page records
6. Update crawl_run status through lifecycle
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from semrush_workers.crawl.js_selector import JsSelector
from semrush_workers.crawl.renderer import RenderedResult, Renderer

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class StorageProtocol(Protocol):
    """Protocol for object storage operations."""

    async def put_object(self, key: str, data: bytes, content_type: str = "text/html") -> str:
        """Store an object and return its key."""
        ...

    async def get_object(self, key: str) -> bytes:
        """Retrieve an object by key."""
        ...


@dataclass
class RenderCandidate:
    """
    A page candidate for JS rendering.

    Attributes:
        page_id: UUID of the crawl page.
        url: URL to render.
        trigger: Name of the heuristic that triggered selection.
    """

    page_id: uuid.UUID
    url: str
    trigger: str


@dataclass
class DefaultOrchestratorSettings:
    """Default settings for the render orchestrator."""

    max_rendered_pages: int = 200
    max_render_time_ms: int = 15000
    concurrency_js: int = 2
    min_text_chars: int = 200
    min_word_count: int = 50
    required_selectors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.required_selectors is None:
            self.required_selectors = []


class RenderOrchestrator:
    """
    Orchestrates the JS rendering flow for hybrid crawling.

    Coordinates selection, rendering, extraction, and storage
    of JavaScript-rendered pages.
    """

    def __init__(
        self,
        settings: Any | None = None,
        renderer: Renderer | None = None,
        storage: Any | None = None,
    ) -> None:
        """
        Initialize the render orchestrator.

        Args:
            settings: Settings object with render configuration.
            renderer: Optional pre-configured renderer.
            storage: Optional storage client for artifacts.
        """
        if settings is None:
            settings = DefaultOrchestratorSettings()

        self._settings = settings
        self._selector = JsSelector(settings=settings)
        self._renderer = renderer or Renderer(settings=settings)
        self._storage = storage

    def select_candidates(
        self,
        pages: list[Any],
        htmls: list[str],
    ) -> list[RenderCandidate]:
        """
        Select pages that need JS rendering.

        Uses heuristics to identify pages that require JavaScript
        rendering, respecting budget limits.

        Args:
            pages: List of page data objects.
            htmls: List of HTML strings (same order as pages).

        Returns:
            List of RenderCandidate objects.
        """
        js_candidates = self._selector.select_candidates(pages, htmls)

        return [
            RenderCandidate(
                page_id=c.page_id,
                url=c.url,
                trigger=c.trigger,
            )
            for c in js_candidates
        ]

    async def render_candidates(
        self,
        candidates: list[RenderCandidate],
    ) -> list[RenderedResult]:
        """
        Render candidate pages with JavaScript execution.

        Args:
            candidates: List of pages to render.

        Returns:
            List of RenderedResult objects.
        """
        urls = [c.url for c in candidates]

        if not urls:
            return []

        results = await self._renderer.render_batch(urls)
        return list(results)

    async def store_rendered_html(
        self,
        page_id: uuid.UUID,
        html: str,
    ) -> str:
        """
        Store rendered HTML to object storage.

        Args:
            page_id: UUID of the page.
            html: Rendered HTML content.

        Returns:
            Storage key for the artifact.
        """
        key = f"rendered/{page_id}/content.html"

        if self._storage:
            await self._storage.put_object(
                key=key,
                data=html.encode("utf-8"),
                content_type="text/html",
            )

        return key

    async def update_status(
        self,
        crawl_run_id: uuid.UUID,
        status: str,
        db_session: Any,
    ) -> None:
        """
        Update crawl run status.

        Args:
            crawl_run_id: UUID of the crawl run.
            status: New status value.
            db_session: Database session.
        """
        # Execute status update
        from sqlalchemy import text

        await db_session.execute(
            text("UPDATE crawl_runs SET status = :status WHERE id = :id"),
            {"status": status, "id": str(crawl_run_id)},
        )
        await db_session.commit()

        logger.info("Updated crawl run %s status to %s", crawl_run_id, status)

    async def update_page_with_rendered_data(
        self,
        page_id: uuid.UUID,
        rendered_html: str,
        render_trigger: str,
        db_session: Any,
    ) -> None:
        """
        Update a page record with rendered data.

        Args:
            page_id: UUID of the page.
            rendered_html: Rendered HTML content.
            render_trigger: Which heuristic triggered rendering.
            db_session: Database session.
        """
        # Compute rendered hash
        rendered_hash = hashlib.sha256(rendered_html.encode()).hexdigest()[:16]

        # Store to storage if available
        artifact_key = await self.store_rendered_html(page_id, rendered_html)

        # Update database record
        from sqlalchemy import text

        await db_session.execute(
            text(
                """
                UPDATE crawl_pages
                SET was_rendered = true,
                    render_trigger = :trigger,
                    rendered_hash = :hash,
                    rendered_artifact_key = :artifact_key
                WHERE id = :id
                """
            ),
            {
                "trigger": render_trigger,
                "hash": rendered_hash,
                "artifact_key": artifact_key,
                "id": str(page_id),
            },
        )
        await db_session.commit()

    async def process_run(
        self,
        crawl_run_id: uuid.UUID,
        pages: list[Any],
        htmls: list[str],
        db_session: Any,
    ) -> dict[str, Any]:
        """
        Process a full rendering run.

        Complete orchestration flow:
        1. Update status to 'selecting_js'
        2. Select candidates using heuristics
        3. Update status to 'rendering_js'
        4. Render candidates
        5. Store rendered HTML and update pages
        6. Update status to 'js_complete' or 'analyzing'

        Args:
            crawl_run_id: UUID of the crawl run.
            pages: List of page data objects.
            htmls: List of HTML strings.
            db_session: Database session.

        Returns:
            Summary dict with pages_selected, pages_rendered, pages_failed.
        """
        try:
            # Step 1: Select candidates
            await self.update_status(crawl_run_id, "selecting_js", db_session)
            candidates = self.select_candidates(pages, htmls)

            logger.info(
                "Selected %d candidates for JS rendering in run %s",
                len(candidates),
                crawl_run_id,
            )

            if not candidates:
                await self.update_status(crawl_run_id, "analyzing", db_session)
                return {
                    "pages_selected": 0,
                    "pages_rendered": 0,
                    "pages_failed": 0,
                }

            # Step 2: Render candidates
            await self.update_status(crawl_run_id, "rendering_js", db_session)
            results = await self.render_candidates(candidates)

            # Step 3: Process results
            pages_rendered = 0
            pages_failed = 0

            for candidate, result in zip(candidates, results, strict=False):
                if result.success and result.html:
                    await self.update_page_with_rendered_data(
                        page_id=candidate.page_id,
                        rendered_html=result.html,
                        render_trigger=candidate.trigger,
                        db_session=db_session,
                    )
                    pages_rendered += 1
                else:
                    pages_failed += 1
                    logger.warning(
                        "Failed to render %s: %s",
                        candidate.url,
                        result.error,
                    )

            # Step 4: Update final status
            await self.update_status(crawl_run_id, "analyzing", db_session)

            return {
                "pages_selected": len(candidates),
                "pages_rendered": pages_rendered,
                "pages_failed": pages_failed,
            }

        except Exception as e:
            logger.exception("Error during render orchestration: %s", e)
            raise

    async def close(self) -> None:
        """Close resources (renderer, connections)."""
        await self._renderer.close()
