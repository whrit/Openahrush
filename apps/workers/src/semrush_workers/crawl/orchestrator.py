"""
Crawl Orchestrator - Main entry point for crawl execution.

Coordinates all crawl components to execute a complete site crawl:
1. HTML crawling phase with frontier management
2. JS candidate selection and rendering
3. SEO rules analysis

Emits events throughout the lifecycle for monitoring and integration.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from semrush_workers.crawl.events import NoOpEventEmitter
from semrush_workers.crawl.fetcher import FetchResult
from semrush_workers.crawl.frontier import Frontier, FrontierSettings
from semrush_workers.crawl.models import (
    AnalysisResult,
    CrawlRun,
    CrawlSettings,
    CrawlStatus,
    PageData,
    RenderedResult,
)

if TYPE_CHECKING:
    from semrush_workers.crawl.events import BaseEventEmitter


# ============================================================================
# Protocol Definitions for Dependencies
# ============================================================================


class FetcherProtocol(Protocol):
    """Protocol for HTTP fetcher."""

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a URL."""
        ...

    async def close(self) -> None:
        """Close connections."""
        ...


class ExtractorProtocol(Protocol):
    """Protocol for HTML extractor."""

    def extract(self, html: bytes, url: str) -> PageData:
        """Extract data from HTML."""
        ...


class RendererProtocol(Protocol):
    """Protocol for JS renderer."""

    async def render(self, url: str) -> RenderedResult:
        """Render a page."""
        ...

    async def render_batch(self, urls: list[str]) -> list[RenderedResult]:
        """Render multiple pages."""
        ...

    async def close(self) -> None:
        """Close browser."""
        ...


class RulesEngineProtocol(Protocol):
    """Protocol for SEO rules engine."""

    async def analyze(
        self,
        crawl_run_id: uuid.UUID,
        pages: list[dict[str, Any]],
    ) -> AnalysisResult:
        """Analyze pages for SEO issues."""
        ...


class StorageProtocol(Protocol):
    """Protocol for crawl data storage."""

    async def create_crawl_run(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        seed_url: str,
        config_snapshot: dict[str, Any],
    ) -> uuid.UUID:
        """Create a crawl run record."""
        ...

    async def update_status(
        self,
        crawl_run_id: uuid.UUID,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update crawl run status."""
        ...

    async def update_metrics(
        self,
        crawl_run_id: uuid.UUID,
        pages_crawled: int | None = None,
        pages_rendered: int | None = None,
        issues_found: int | None = None,
    ) -> None:
        """Update crawl run metrics."""
        ...

    async def store_page(
        self,
        crawl_run_id: uuid.UUID,
        url: str,
        depth: int,
        fetch_result: FetchResult,
        page_data: PageData | None,
        discovery_source: str,
    ) -> uuid.UUID:
        """Store a crawled page."""
        ...

    async def store_link_edge(
        self,
        crawl_run_id: uuid.UUID,
        source_url: str,
        target_url: str,
        anchor_text: str | None,
        is_internal: bool,
        is_follow: bool,
    ) -> uuid.UUID:
        """Store a link edge."""
        ...

    async def get_pages_for_analysis(
        self,
        crawl_run_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Get pages for analysis."""
        ...

    async def get_js_candidates(
        self,
        crawl_run_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Get JS rendering candidates."""
        ...


# ============================================================================
# CrawlOrchestrator
# ============================================================================


@dataclass
class CrawlOrchestrator:
    """
    Orchestrates a complete site crawl.

    Coordinates frontier, fetcher, extractor, renderer, and rules engine
    to execute a full crawl lifecycle with proper status tracking and
    event emission.

    Attributes:
        project_id: ID of the project being crawled.
        site_id: ID of the site being crawled.
        seed_url: Starting URL for the crawl.
        settings: Crawl configuration settings.
        db_session: Database session for transactions.
        storage: Storage interface for persisting crawl data.
        fetcher: HTTP fetcher for page retrieval.
        extractor: HTML extractor for parsing pages.
        renderer: JS renderer for dynamic content.
        rules_engine: SEO rules engine for analysis.
        event_emitter: Event emitter for lifecycle events.
    """

    project_id: uuid.UUID
    site_id: uuid.UUID
    seed_url: str
    settings: CrawlSettings
    db_session: Any

    # Optional dependencies (can be injected for testing)
    storage: StorageProtocol | None = None
    fetcher: FetcherProtocol | None = None
    extractor: ExtractorProtocol | None = None
    renderer: RendererProtocol | None = None
    rules_engine: RulesEngineProtocol | None = None
    event_emitter: BaseEventEmitter | None = None

    # Internal state
    _crawl_run: CrawlRun | None = field(default=None, init=False)
    _frontier: Frontier | None = field(default=None, init=False)
    _pages_crawled: int = field(default=0, init=False)
    _pages_rendered: int = field(default=0, init=False)
    _js_candidates: list[uuid.UUID] = field(default_factory=list, init=False)
    _crawled_pages: list[dict[str, Any]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        """Initialize default dependencies if not provided."""
        if self.event_emitter is None:
            self.event_emitter = NoOpEventEmitter()

    async def start(self) -> CrawlRun:
        """
        Start the crawl by creating a crawl run record.

        Creates the crawl_run record in the database, initializes the
        frontier with the seed URL, and emits the crawl.started event.

        Returns:
            The created CrawlRun object.
        """
        # Create config snapshot
        config_snapshot = {
            "max_pages": self.settings.max_pages,
            "max_depth": self.settings.max_depth,
            "user_agent": self.settings.user_agent,
            "render_js": self.settings.render_js,
            "js_render_budget": self.settings.js_render_budget,
            "respect_robots_txt": self.settings.respect_robots_txt,
            "use_sitemaps": self.settings.use_sitemaps,
        }

        # Create crawl run in storage
        if self.storage:
            run_id = await self.storage.create_crawl_run(
                project_id=self.project_id,
                site_id=self.site_id,
                seed_url=self.seed_url,
                config_snapshot=config_snapshot,
            )
        else:
            run_id = uuid.uuid4()

        # Create CrawlRun object
        self._crawl_run = CrawlRun(
            id=run_id,
            project_id=self.project_id,
            site_id=self.site_id,
            status=CrawlStatus.RUNNING,
            config_snapshot=config_snapshot,
            seed_url=self.seed_url,
            started_at=datetime.now(UTC),
        )

        # Initialize frontier
        frontier_settings = FrontierSettings(
            max_depth=self.settings.max_depth,
            max_pages=self.settings.max_pages,
        )
        self._frontier = Frontier(
            seed_url=self.seed_url,
            settings=frontier_settings,
        )

        # Emit started event
        if self.event_emitter:
            await self.event_emitter.emit_crawl_started(
                project_id=self.project_id,
                crawl_run_id=run_id,
                seed_url=self.seed_url,
                config=config_snapshot,
            )

        return self._crawl_run

    async def run_html_phase(self) -> int:
        """
        Execute the HTML crawling phase.

        Fetches pages from the frontier, extracts content, and stores
        crawl_page records. Discovers new URLs and adds them to frontier.

        Returns:
            Number of pages crawled.
        """
        if not self._crawl_run or not self._frontier:
            raise RuntimeError("Crawl not started. Call start() first.")

        self._pages_crawled = 0
        crawl_run_id = self._crawl_run.id

        # Main crawl loop
        while self._frontier.has_pending():
            result = self._frontier.pop()
            if result is None:
                break

            depth, url = result
            self._pages_crawled += 1

            # Fetch the page
            if self.fetcher:
                fetch_result = await self.fetcher.fetch(url)
            else:
                # Create a default fetch result for testing without fetcher
                fetch_result = FetchResult(
                    url=url,
                    final_url=url,
                    status_code=200,
                    content_type="text/html",
                    body=b"<html><body>Test</body></html>",
                    response_time_ms=100,
                    headers={},
                )

            # Extract page data if HTML
            page_data: PageData | None = None
            if fetch_result.status_code == 200 and fetch_result.content_type:
                if "text/html" in fetch_result.content_type.lower():
                    if self.extractor:
                        page_data = self.extractor.extract(fetch_result.body, url)
                    else:
                        page_data = PageData(title="Test", word_count=100, text_length=500)

            # Store the page
            discovery_source = "seed" if depth == 0 else "internal_link"
            if self.storage:
                page_id = await self.storage.store_page(
                    crawl_run_id=crawl_run_id,
                    url=url,
                    depth=depth,
                    fetch_result=fetch_result,
                    page_data=page_data,
                    discovery_source=discovery_source,
                )

                # Track for analysis
                self._crawled_pages.append({
                    "id": page_id,
                    "url": url,
                    "status_code": fetch_result.status_code,
                    "page_data": page_data,
                })

            # Emit page fetched event
            if self.event_emitter:
                await self.event_emitter.emit_page_fetched(
                    project_id=self.project_id,
                    crawl_run_id=crawl_run_id,
                    url=url,
                    status_code=fetch_result.status_code,
                    response_time_ms=fetch_result.response_time_ms,
                )

            # Add discovered links to frontier
            if page_data:
                for link in page_data.internal_links:
                    if not self._frontier.is_at_capacity():
                        added = self._frontier.add(link.url, depth + 1)
                        if added and self.storage:
                            await self.storage.store_link_edge(
                                crawl_run_id=crawl_run_id,
                                source_url=url,
                                target_url=link.url,
                                anchor_text=link.anchor_text,
                                is_internal=True,
                                is_follow=link.is_follow,
                            )

                # Store external links too
                for link in page_data.external_links:
                    if self.storage:
                        await self.storage.store_link_edge(
                            crawl_run_id=crawl_run_id,
                            source_url=url,
                            target_url=link.url,
                            anchor_text=link.anchor_text,
                            is_internal=False,
                            is_follow=link.is_follow,
                        )

        # Update status to html_complete
        if self.storage:
            await self.storage.update_status(crawl_run_id, CrawlStatus.HTML_COMPLETE)
            await self.storage.update_metrics(crawl_run_id, pages_crawled=self._pages_crawled)

        self._crawl_run.status = CrawlStatus.HTML_COMPLETE
        self._crawl_run.pages_crawled = self._pages_crawled

        # Emit html_complete event
        if self.event_emitter:
            await self.event_emitter.emit_html_complete(
                project_id=self.project_id,
                crawl_run_id=crawl_run_id,
                pages_crawled=self._pages_crawled,
            )

        return self._pages_crawled

    async def run_js_selection(self) -> list[uuid.UUID]:
        """
        Select pages that need JavaScript rendering.

        Uses heuristics to identify pages with thin DOM, SPA shells,
        or missing required selectors.

        Returns:
            List of page IDs selected for JS rendering.
        """
        if not self._crawl_run:
            raise RuntimeError("Crawl not started. Call start() first.")

        crawl_run_id = self._crawl_run.id

        # Get candidates from storage
        if self.storage:
            candidates_data = await self.storage.get_js_candidates(crawl_run_id)
        else:
            candidates_data = []

        # Apply JS render budget
        budget = self.settings.js_render_budget
        candidates: list[uuid.UUID] = []
        for c in candidates_data[:budget]:
            page_id = c.get("id")
            if page_id is not None and isinstance(page_id, uuid.UUID):
                candidates.append(page_id)
        self._js_candidates = candidates

        return self._js_candidates

    async def run_js_render_phase(self) -> int:
        """
        Execute JavaScript rendering for selected pages.

        Renders pages using Playwright and re-extracts content.

        Returns:
            Number of pages rendered.
        """
        if not self._crawl_run:
            raise RuntimeError("Crawl not started. Call start() first.")

        crawl_run_id = self._crawl_run.id
        self._pages_rendered = 0

        if not self.settings.render_js:
            # JS rendering disabled
            if self.storage:
                await self.storage.update_status(crawl_run_id, CrawlStatus.JS_COMPLETE)
            self._crawl_run.status = CrawlStatus.JS_COMPLETE

            if self.event_emitter:
                await self.event_emitter.emit_js_complete(
                    project_id=self.project_id,
                    crawl_run_id=crawl_run_id,
                    pages_rendered=0,
                )

            return 0

        # Update status to JS_RENDERING
        if self.storage:
            await self.storage.update_status(crawl_run_id, CrawlStatus.JS_RENDERING)

        # Render candidates
        if self.renderer and self._js_candidates:
            # Get URLs for candidates (simplified - in real impl would query storage)
            urls_to_render = []
            for page in self._crawled_pages:
                if page.get("id") in self._js_candidates:
                    urls_to_render.append(page.get("url", ""))

            if urls_to_render:
                results = await self.renderer.render_batch(urls_to_render)
                self._pages_rendered = sum(1 for r in results if r.success)

        # Update status to JS_COMPLETE
        if self.storage:
            await self.storage.update_status(crawl_run_id, CrawlStatus.JS_COMPLETE)
            await self.storage.update_metrics(crawl_run_id, pages_rendered=self._pages_rendered)

        self._crawl_run.status = CrawlStatus.JS_COMPLETE
        self._crawl_run.pages_rendered = self._pages_rendered

        # Emit js_complete event
        if self.event_emitter:
            await self.event_emitter.emit_js_complete(
                project_id=self.project_id,
                crawl_run_id=crawl_run_id,
                pages_rendered=self._pages_rendered,
            )

        return self._pages_rendered

    async def run_analysis_phase(self) -> AnalysisResult:
        """
        Execute SEO analysis on crawled pages.

        Runs the rules engine to detect issues and compute impact scores.

        Returns:
            AnalysisResult with detected issues.
        """
        if not self._crawl_run:
            raise RuntimeError("Crawl not started. Call start() first.")

        crawl_run_id = self._crawl_run.id

        # Update status to ANALYZING
        if self.storage:
            await self.storage.update_status(crawl_run_id, CrawlStatus.ANALYZING)
            pages = await self.storage.get_pages_for_analysis(crawl_run_id)
        else:
            pages = self._crawled_pages

        # Run analysis
        if self.rules_engine:
            result = await self.rules_engine.analyze(crawl_run_id, pages)
        else:
            result = AnalysisResult(
                issues_found=0,
                pages_analyzed=len(pages),
                duration_seconds=0.0,
            )

        # Update status to COMPLETED
        if self.storage:
            await self.storage.update_status(crawl_run_id, CrawlStatus.COMPLETED)
            await self.storage.update_metrics(crawl_run_id, issues_found=result.issues_found)

        self._crawl_run.status = CrawlStatus.COMPLETED
        self._crawl_run.issues_found = result.issues_found
        self._crawl_run.completed_at = datetime.now(UTC)

        # Emit completed event
        if self.event_emitter:
            duration = 0.0
            if self._crawl_run.started_at:
                duration = (
                    datetime.now(UTC) - self._crawl_run.started_at
                ).total_seconds()

            await self.event_emitter.emit_crawl_completed(
                project_id=self.project_id,
                crawl_run_id=crawl_run_id,
                pages_crawled=self._pages_crawled,
                pages_rendered=self._pages_rendered,
                issues_found=result.issues_found,
                duration_seconds=duration,
            )

        return result

    async def run(self) -> CrawlRun:
        """
        Execute a complete crawl.

        Runs all phases in sequence: start, HTML crawl, JS selection,
        JS rendering, and analysis.

        Returns:
            The completed CrawlRun object.
        """
        try:
            await self.start()
            await self.run_html_phase()
            await self.run_js_selection()
            await self.run_js_render_phase()
            await self.run_analysis_phase()

            if self._crawl_run:
                return self._crawl_run

            raise RuntimeError("Crawl run not initialized")

        except Exception as e:
            # Handle failure
            if self._crawl_run and self.storage:
                await self.storage.update_status(
                    self._crawl_run.id,
                    CrawlStatus.FAILED,
                    error_message=str(e),
                )

            if self._crawl_run and self.event_emitter:
                await self.event_emitter.emit_crawl_failed(
                    project_id=self.project_id,
                    crawl_run_id=self._crawl_run.id,
                    error_message=str(e),
                )

            if self._crawl_run:
                self._crawl_run.status = CrawlStatus.FAILED
                self._crawl_run.error_message = str(e)

            raise
