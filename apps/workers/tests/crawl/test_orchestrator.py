"""
TDD tests for the Crawl Orchestrator.

Tests cover the full orchestration flow including:
- Normal crawl completion
- Budget limits (max_pages, max_depth)
- Error handling (fetch failures, render failures)
- Status transitions
- Event emission
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import pytest
from semrush_workers.crawl.events import EventType, NoOpEventEmitter
from semrush_workers.crawl.fetcher import FetchResult
from semrush_workers.crawl.models import (
    AnalysisResult,
    CrawlSettings,
    CrawlStatus,
    Link,
    PageData,
    RenderedResult,
)

# ============================================================================
# Mock Implementations for Testing
# ============================================================================


@dataclass
class MockFrontier:
    """Mock frontier for testing orchestrator."""

    seed_url: str
    max_pages: int = 500
    max_depth: int = 10
    _queue: list[tuple[int, str]] = field(default_factory=list, init=False)
    _seen: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self._queue.append((0, self.seed_url))
        self._seen.add(self.seed_url)

    def add(self, url: str, depth: int) -> bool:
        if depth > self.max_depth:
            return False
        if len(self._seen) >= self.max_pages:
            return False
        if url in self._seen:
            return False
        self._seen.add(url)
        self._queue.append((depth, url))
        return True

    def pop(self) -> tuple[int, str] | None:
        if not self._queue:
            return None
        return self._queue.pop(0)

    def size(self) -> int:
        return len(self._queue)

    def total_seen(self) -> int:
        return len(self._seen)

    def is_at_capacity(self) -> bool:
        return len(self._seen) >= self.max_pages

    def has_pending(self) -> bool:
        return len(self._queue) > 0


class MockFetcher:
    """Mock fetcher for testing orchestrator."""

    def __init__(self) -> None:
        self.responses: dict[str, FetchResult] = {}
        self.fetch_count = 0
        self.failed_urls: set[str] = set()

    def set_response(self, url: str, result: FetchResult) -> None:
        self.responses[url] = result

    def set_failure(self, url: str) -> None:
        self.failed_urls.add(url)

    async def fetch(self, url: str) -> FetchResult:
        self.fetch_count += 1
        if url in self.failed_urls:
            return FetchResult(
                url=url,
                final_url=url,
                status_code=0,
                content_type=None,
                body=b"",
                response_time_ms=0,
                headers={},
            )
        if url in self.responses:
            return self.responses[url]
        # Default successful HTML response
        return FetchResult(
            url=url,
            final_url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            body=b"<html><head><title>Test</title></head><body><h1>Test</h1></body></html>",
            response_time_ms=100,
            headers={"content-type": "text/html; charset=utf-8"},
        )

    async def close(self) -> None:
        pass


class MockExtractor:
    """Mock HTML extractor for testing orchestrator."""

    def __init__(self) -> None:
        self.extracted_pages: dict[str, PageData] = {}

    def set_page_data(self, url: str, page_data: PageData) -> None:
        self.extracted_pages[url] = page_data

    def extract(self, html: bytes, url: str) -> PageData:
        if url in self.extracted_pages:
            return self.extracted_pages[url]
        # Default page data
        return PageData(
            title="Test Page",
            meta_description="A test page",
            h1_count=1,
            first_h1="Test",
            word_count=100,
            text_length=500,
            internal_links=[],
            external_links=[],
            scripts=[],
        )


class MockRenderer:
    """Mock JS renderer for testing orchestrator."""

    def __init__(self) -> None:
        self.rendered_pages: dict[str, RenderedResult] = {}
        self.render_count = 0
        self.failed_urls: set[str] = set()

    def set_result(self, url: str, result: RenderedResult) -> None:
        self.rendered_pages[url] = result

    def set_failure(self, url: str) -> None:
        self.failed_urls.add(url)

    async def render(self, url: str) -> RenderedResult:
        self.render_count += 1
        if url in self.failed_urls:
            return RenderedResult(url=url, html=None, success=False, error="Render failed")
        if url in self.rendered_pages:
            return self.rendered_pages[url]
        return RenderedResult(
            url=url,
            html="<html><body><h1>Rendered</h1></body></html>",
            success=True,
            render_time_ms=500,
        )

    async def render_batch(self, urls: list[str]) -> list[RenderedResult]:
        return [await self.render(url) for url in urls]

    async def close(self) -> None:
        pass


class MockRulesEngine:
    """Mock rules engine for testing orchestrator."""

    def __init__(self) -> None:
        self.issues_to_return = 0
        self.analyze_called = False

    async def analyze(
        self,
        crawl_run_id: uuid.UUID,
        pages: list[dict[str, Any]],
    ) -> AnalysisResult:
        self.analyze_called = True
        return AnalysisResult(
            issues_found=self.issues_to_return,
            pages_analyzed=len(pages),
            duration_seconds=1.5,
            issues_by_severity={"low": 5, "medium": 3, "high": 2},
            top_issues=["missing_title", "thin_content"],
        )


class MockStorage:
    """Mock storage for testing orchestrator."""

    def __init__(self) -> None:
        self.crawl_runs: dict[uuid.UUID, dict[str, Any]] = {}
        self.pages: dict[uuid.UUID, dict[str, Any]] = {}
        self.link_edges: list[dict[str, Any]] = []

    async def create_crawl_run(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        seed_url: str,
        config_snapshot: dict[str, Any],
    ) -> uuid.UUID:
        run_id = uuid.uuid4()
        self.crawl_runs[run_id] = {
            "id": run_id,
            "project_id": project_id,
            "site_id": site_id,
            "seed_url": seed_url,
            "config_snapshot": config_snapshot,
            "status": CrawlStatus.PENDING,
            "pages_crawled": 0,
            "pages_rendered": 0,
            "issues_found": 0,
        }
        return run_id

    async def update_status(
        self,
        crawl_run_id: uuid.UUID,
        status: str,
        error_message: str | None = None,
    ) -> None:
        if crawl_run_id in self.crawl_runs:
            self.crawl_runs[crawl_run_id]["status"] = status
            if error_message:
                self.crawl_runs[crawl_run_id]["error_message"] = error_message

    async def update_metrics(
        self,
        crawl_run_id: uuid.UUID,
        pages_crawled: int | None = None,
        pages_rendered: int | None = None,
        issues_found: int | None = None,
    ) -> None:
        if crawl_run_id in self.crawl_runs:
            run = self.crawl_runs[crawl_run_id]
            if pages_crawled is not None:
                run["pages_crawled"] = pages_crawled
            if pages_rendered is not None:
                run["pages_rendered"] = pages_rendered
            if issues_found is not None:
                run["issues_found"] = issues_found

    async def store_page(
        self,
        crawl_run_id: uuid.UUID,
        url: str,
        depth: int,
        fetch_result: FetchResult,
        page_data: PageData | None,
        discovery_source: str,
    ) -> uuid.UUID:
        page_id = uuid.uuid4()
        self.pages[page_id] = {
            "id": page_id,
            "crawl_run_id": crawl_run_id,
            "url": url,
            "depth": depth,
            "status_code": fetch_result.status_code,
            "page_data": page_data,
            "discovery_source": discovery_source,
        }
        return page_id

    async def store_link_edge(
        self,
        crawl_run_id: uuid.UUID,
        source_url: str,
        target_url: str,
        anchor_text: str | None,
        is_internal: bool,
        is_follow: bool,
    ) -> uuid.UUID:
        edge_id = uuid.uuid4()
        self.link_edges.append({
            "id": edge_id,
            "crawl_run_id": crawl_run_id,
            "source_url": source_url,
            "target_url": target_url,
            "anchor_text": anchor_text,
            "is_internal": is_internal,
            "is_follow": is_follow,
        })
        return edge_id

    async def get_pages_for_analysis(
        self,
        crawl_run_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        return [
            p for p in self.pages.values()
            if p["crawl_run_id"] == crawl_run_id
        ]

    async def get_js_candidates(
        self,
        crawl_run_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        # Return pages that need JS rendering (mock logic)
        return []


class MockDbSession:
    """Mock database session for testing."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def project_id() -> uuid.UUID:
    """Sample project ID."""
    return uuid.uuid4()


@pytest.fixture
def site_id() -> uuid.UUID:
    """Sample site ID."""
    return uuid.uuid4()


@pytest.fixture
def crawl_settings() -> CrawlSettings:
    """Default crawl settings for testing."""
    return CrawlSettings(
        max_pages=100,
        max_depth=5,
        user_agent="TestBot/1.0",
        render_js=True,
        js_render_budget=10,
        respect_robots_txt=True,
        use_sitemaps=False,
        politeness_delay_ms=0,  # No delay for tests
    )


@pytest.fixture
def mock_fetcher() -> MockFetcher:
    """Create mock fetcher."""
    return MockFetcher()


@pytest.fixture
def mock_extractor() -> MockExtractor:
    """Create mock extractor."""
    return MockExtractor()


@pytest.fixture
def mock_renderer() -> MockRenderer:
    """Create mock renderer."""
    return MockRenderer()


@pytest.fixture
def mock_rules_engine() -> MockRulesEngine:
    """Create mock rules engine."""
    return MockRulesEngine()


@pytest.fixture
def mock_storage() -> MockStorage:
    """Create mock storage."""
    return MockStorage()


@pytest.fixture
def mock_db_session() -> MockDbSession:
    """Create mock DB session."""
    return MockDbSession()


@pytest.fixture
def event_emitter() -> NoOpEventEmitter:
    """Create no-op event emitter for testing."""
    return NoOpEventEmitter()


# ============================================================================
# Tests for CrawlOrchestrator
# ============================================================================


class TestCrawlOrchestratorInit:
    """Tests for orchestrator initialization."""

    def test_orchestrator_requires_project_id(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_db_session: MockDbSession,
    ) -> None:
        """Orchestrator should require a project_id."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=mock_db_session,
        )
        assert orchestrator.project_id == project_id

    def test_orchestrator_requires_site_id(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_db_session: MockDbSession,
    ) -> None:
        """Orchestrator should require a site_id."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=mock_db_session,
        )
        assert orchestrator.site_id == site_id

    def test_orchestrator_accepts_settings(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_db_session: MockDbSession,
    ) -> None:
        """Orchestrator should accept crawl settings."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=mock_db_session,
        )
        assert orchestrator.settings.max_pages == 100
        assert orchestrator.settings.max_depth == 5


class TestCrawlOrchestratorStart:
    """Tests for starting a crawl."""

    @pytest.mark.asyncio
    async def test_start_creates_crawl_run(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """Starting a crawl should create a crawl_run record."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        crawl_run = await orchestrator.start()

        assert crawl_run is not None
        assert crawl_run.project_id == project_id
        assert crawl_run.site_id == site_id
        assert crawl_run.seed_url == "https://example.com"
        assert len(mock_storage.crawl_runs) == 1

    @pytest.mark.asyncio
    async def test_start_emits_started_event(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """Starting a crawl should emit crawl.started event."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()

        started_events = event_emitter.get_events_by_type(EventType.CRAWL_STARTED)
        assert len(started_events) == 1
        assert started_events[0].payload["seed_url"] == "https://example.com"


class TestCrawlOrchestratorHtmlPhase:
    """Tests for the HTML crawling phase."""

    @pytest.mark.asyncio
    async def test_run_html_phase_fetches_pages(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """HTML phase should fetch pages from the frontier."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        pages_crawled = await orchestrator.run_html_phase()

        assert pages_crawled >= 1
        assert mock_fetcher.fetch_count >= 1

    @pytest.mark.asyncio
    async def test_run_html_phase_respects_max_pages(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """HTML phase should respect max_pages limit."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        settings = CrawlSettings(max_pages=3, max_depth=10)

        # Set up fetcher to return pages with links
        mock_fetcher.set_response(
            "https://example.com",
            FetchResult(
                url="https://example.com",
                final_url="https://example.com",
                status_code=200,
                content_type="text/html",
                body=b"<html><body><a href='/page1'>Link</a></body></html>",
                response_time_ms=100,
                headers={},
            ),
        )

        # Set up extractor to return links
        mock_extractor.set_page_data(
            "https://example.com",
            PageData(
                title="Home",
                internal_links=[
                    Link(url="https://example.com/page1"),
                    Link(url="https://example.com/page2"),
                    Link(url="https://example.com/page3"),
                    Link(url="https://example.com/page4"),
                ],
            ),
        )

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        pages_crawled = await orchestrator.run_html_phase()

        # Should stop at max_pages=3
        assert pages_crawled <= 3

    @pytest.mark.asyncio
    async def test_run_html_phase_respects_max_depth(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """HTML phase should respect max_depth limit."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        settings = CrawlSettings(max_pages=100, max_depth=1)

        # Note: URLs are normalized by frontier, so use normalized forms
        # https://example.com -> https://example.com/
        mock_extractor.set_page_data(
            "https://example.com/",
            PageData(
                title="Home",
                internal_links=[Link(url="https://example.com/level1")],
            ),
        )
        mock_extractor.set_page_data(
            "https://example.com/level1",
            PageData(
                title="Level 1",
                internal_links=[Link(url="https://example.com/level2")],
            ),
        )

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        pages_crawled = await orchestrator.run_html_phase()

        # Should only crawl depth 0 and 1, not depth 2
        assert pages_crawled == 2

    @pytest.mark.asyncio
    async def test_run_html_phase_handles_fetch_errors(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """HTML phase should handle fetch failures gracefully."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        # Mark URL as failing
        mock_fetcher.set_failure("https://example.com")

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        # Should not raise, should handle gracefully
        pages_crawled = await orchestrator.run_html_phase()

        assert pages_crawled >= 0  # Even failed fetches count as attempts

    @pytest.mark.asyncio
    async def test_run_html_phase_stores_pages(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """HTML phase should store crawled pages."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        await orchestrator.run_html_phase()

        assert len(mock_storage.pages) >= 1

    @pytest.mark.asyncio
    async def test_run_html_phase_emits_page_fetched_events(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """HTML phase should emit page_fetched events."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        await orchestrator.run_html_phase()

        page_events = event_emitter.get_events_by_type(EventType.CRAWL_PAGE_FETCHED)
        assert len(page_events) >= 1


class TestCrawlOrchestratorJsPhase:
    """Tests for JS rendering phase."""

    @pytest.mark.asyncio
    async def test_run_js_selection_returns_candidates(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """JS selection should return page IDs for rendering."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        await orchestrator.run_html_phase()
        candidates = await orchestrator.run_js_selection()

        # Should return a list (possibly empty)
        assert isinstance(candidates, list)

    @pytest.mark.asyncio
    async def test_run_js_render_phase_renders_candidates(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """JS render phase should render selected candidates."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        # Set up page with thin content (needs JS rendering)
        mock_extractor.set_page_data(
            "https://example.com",
            PageData(
                title="SPA Shell",
                word_count=10,  # Thin content
                text_length=50,
                scripts=["app.12345.js"],  # SPA bundle pattern
            ),
        )

        settings = CrawlSettings(
            max_pages=10,
            render_js=True,
            js_render_budget=5,
        )

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        await orchestrator.run_html_phase()
        await orchestrator.run_js_selection()
        pages_rendered = await orchestrator.run_js_render_phase()

        assert isinstance(pages_rendered, int)

    @pytest.mark.asyncio
    async def test_run_js_render_phase_respects_budget(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """JS render phase should respect render budget."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        settings = CrawlSettings(
            max_pages=100,
            render_js=True,
            js_render_budget=2,  # Only render 2 pages
        )

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        await orchestrator.run_html_phase()
        await orchestrator.run_js_selection()
        pages_rendered = await orchestrator.run_js_render_phase()

        assert pages_rendered <= 2


class TestCrawlOrchestratorAnalysisPhase:
    """Tests for analysis phase."""

    @pytest.mark.asyncio
    async def test_run_analysis_phase_calls_rules_engine(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """Analysis phase should invoke the rules engine."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        mock_rules_engine.issues_to_return = 10

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        await orchestrator.run_html_phase()
        result = await orchestrator.run_analysis_phase()

        assert mock_rules_engine.analyze_called
        assert result.issues_found == 10

    @pytest.mark.asyncio
    async def test_run_analysis_phase_returns_result(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """Analysis phase should return AnalysisResult."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        await orchestrator.run_html_phase()
        result = await orchestrator.run_analysis_phase()

        assert isinstance(result, AnalysisResult)
        assert result.pages_analyzed >= 0
        assert result.duration_seconds >= 0


class TestCrawlOrchestratorStatusTransitions:
    """Tests for status transitions during crawl lifecycle."""

    @pytest.mark.asyncio
    async def test_status_transitions_through_lifecycle(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """Crawl should transition through expected statuses."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        # Start -> RUNNING
        crawl_run = await orchestrator.start()
        run_id = crawl_run.id

        # After HTML phase -> HTML_COMPLETE
        await orchestrator.run_html_phase()
        assert mock_storage.crawl_runs[run_id]["status"] == CrawlStatus.HTML_COMPLETE

        # After JS phase -> JS_COMPLETE
        await orchestrator.run_js_selection()
        await orchestrator.run_js_render_phase()
        assert mock_storage.crawl_runs[run_id]["status"] == CrawlStatus.JS_COMPLETE

        # After analysis -> COMPLETED
        await orchestrator.run_analysis_phase()
        assert mock_storage.crawl_runs[run_id]["status"] == CrawlStatus.COMPLETED


class TestCrawlOrchestratorEventEmission:
    """Tests for event emission during crawl."""

    @pytest.mark.asyncio
    async def test_emits_html_complete_event(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """Should emit html_complete event after HTML phase."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        await orchestrator.run_html_phase()

        html_complete_events = event_emitter.get_events_by_type(EventType.CRAWL_HTML_COMPLETE)
        assert len(html_complete_events) == 1

    @pytest.mark.asyncio
    async def test_emits_js_complete_event(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """Should emit js_complete event after JS phase."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        await orchestrator.run_html_phase()
        await orchestrator.run_js_selection()
        await orchestrator.run_js_render_phase()

        js_complete_events = event_emitter.get_events_by_type(EventType.CRAWL_JS_COMPLETE)
        assert len(js_complete_events) == 1

    @pytest.mark.asyncio
    async def test_emits_completed_event(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """Should emit completed event after full crawl."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        await orchestrator.start()
        await orchestrator.run_html_phase()
        await orchestrator.run_js_selection()
        await orchestrator.run_js_render_phase()
        await orchestrator.run_analysis_phase()

        completed_events = event_emitter.get_events_by_type(EventType.CRAWL_COMPLETED)
        assert len(completed_events) == 1


class TestCrawlOrchestratorFullRun:
    """Tests for full crawl execution."""

    @pytest.mark.asyncio
    async def test_run_executes_full_crawl(
        self,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        crawl_settings: CrawlSettings,
        mock_storage: MockStorage,
        mock_fetcher: MockFetcher,
        mock_extractor: MockExtractor,
        mock_renderer: MockRenderer,
        mock_rules_engine: MockRulesEngine,
        event_emitter: NoOpEventEmitter,
    ) -> None:
        """run() should execute the full crawl lifecycle."""
        from semrush_workers.crawl.orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator(
            project_id=project_id,
            site_id=site_id,
            seed_url="https://example.com",
            settings=crawl_settings,
            db_session=AsyncMock(),
            storage=mock_storage,
            fetcher=mock_fetcher,
            extractor=mock_extractor,
            renderer=mock_renderer,
            rules_engine=mock_rules_engine,
            event_emitter=event_emitter,
        )

        result = await orchestrator.run()

        assert result is not None
        assert result.status == CrawlStatus.COMPLETED

        # Verify all events were emitted
        assert len(event_emitter.get_events_by_type(EventType.CRAWL_STARTED)) == 1
        assert len(event_emitter.get_events_by_type(EventType.CRAWL_HTML_COMPLETE)) == 1
        assert len(event_emitter.get_events_by_type(EventType.CRAWL_JS_COMPLETE)) == 1
        assert len(event_emitter.get_events_by_type(EventType.CRAWL_COMPLETED)) == 1
