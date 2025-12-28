"""
Tests for JS candidate selector.

TDD tests covering:
- Querying crawl_pages with was_rendered=false
- Applying heuristics in priority order
- Respecting max_rendered_pages budget
- Recording which heuristic triggered selection
- Returning list of candidates with trigger reasons
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class MockCrawlPage:
    """Mock crawl page for testing."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    url: str = "https://example.com/page"
    html_artifact_key: str = "artifacts/page.html"
    was_rendered: bool = False
    render_trigger: str | None = None
    text_length: int = 500
    word_count: int = 100
    scripts: list[str] = field(default_factory=list)


@dataclass
class MockCrawlRun:
    """Mock crawl run for testing."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    project_id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: str = "html_complete"
    config_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class MockJsSelectorSettings:
    """Mock settings for JS selector testing."""

    max_rendered_pages: int = 200
    min_text_chars: int = 200
    min_word_count: int = 50
    required_selectors: list[str] = field(default_factory=list)


class TestJsCandidateResult:
    """Tests for JsCandidateResult dataclass."""

    def test_create_candidate_result(self) -> None:
        """Can create a candidate result with trigger reason."""
        from semrush_workers.crawl.js_selector import JsCandidateResult

        page_id = uuid.uuid4()
        result = JsCandidateResult(
            page_id=page_id,
            url="https://example.com",
            trigger="thin_dom",
        )
        assert result.page_id == page_id
        assert result.url == "https://example.com"
        assert result.trigger == "thin_dom"


class TestJsSelectorBasics:
    """Basic JS selector tests."""

    @pytest.mark.asyncio
    async def test_create_selector(self) -> None:
        """Can create a JS selector instance."""
        from semrush_workers.crawl.js_selector import JsSelector

        selector = JsSelector()
        assert selector is not None

    @pytest.mark.asyncio
    async def test_selector_with_settings(self) -> None:
        """Can create selector with custom settings."""
        from semrush_workers.crawl.js_selector import JsSelector

        settings = MockJsSelectorSettings(max_rendered_pages=50)
        selector = JsSelector(settings=settings)
        assert selector.max_rendered_pages == 50


class TestJsSelectorHeuristicApplication:
    """Tests for heuristic application."""

    @pytest.mark.asyncio
    async def test_applies_thin_dom_heuristic(self) -> None:
        """Thin DOM pages should be selected."""
        from semrush_workers.crawl.js_selector import JsSelector

        page = MockCrawlPage(text_length=50, word_count=10)
        settings = MockJsSelectorSettings()
        selector = JsSelector(settings=settings)

        html = "<html><body><div></div></body></html>"
        trigger = selector.get_trigger_for_page(page, html)

        assert trigger == "thin_dom"

    @pytest.mark.asyncio
    async def test_applies_spa_shell_heuristic(self) -> None:
        """SPA shell pages should be selected."""
        from semrush_workers.crawl.js_selector import JsSelector

        page = MockCrawlPage(
            text_length=500,
            word_count=100,
            scripts=["app.abc123.js"],
        )
        settings = MockJsSelectorSettings()
        selector = JsSelector(settings=settings)

        html = """
        <html><body>
            <div id="root"></div>
            <script src="app.abc123.js"></script>
        </body></html>
        """
        trigger = selector.get_trigger_for_page(page, html)

        assert trigger == "spa_shell"

    @pytest.mark.asyncio
    async def test_applies_missing_selectors_heuristic(self) -> None:
        """Missing required selectors should trigger selection."""
        from semrush_workers.crawl.js_selector import JsSelector

        page = MockCrawlPage(text_length=500, word_count=100)
        settings = MockJsSelectorSettings(required_selectors=["h1", ".content"])
        selector = JsSelector(settings=settings)

        html = "<html><body><div>No h1 here</div></body></html>"
        trigger = selector.get_trigger_for_page(page, html)

        assert trigger == "missing_selectors"

    @pytest.mark.asyncio
    async def test_applies_client_redirect_heuristic(self) -> None:
        """Client-side redirects should trigger selection."""
        from semrush_workers.crawl.js_selector import JsSelector

        page = MockCrawlPage(text_length=500, word_count=100)
        settings = MockJsSelectorSettings()
        selector = JsSelector(settings=settings)

        html = """
        <html>
        <head><script>window.location = '/redirect';</script></head>
        <body><div>Content</div></body>
        </html>
        """
        trigger = selector.get_trigger_for_page(page, html)

        assert trigger == "client_redirect"

    @pytest.mark.asyncio
    async def test_no_trigger_for_normal_page(self) -> None:
        """Normal pages should not be selected."""
        from semrush_workers.crawl.js_selector import JsSelector

        page = MockCrawlPage(text_length=500, word_count=100)
        settings = MockJsSelectorSettings()
        selector = JsSelector(settings=settings)

        html = """
        <html>
        <body>
            <h1>Title</h1>
            <main><p>Normal content here with lots of text.</p></main>
        </body>
        </html>
        """
        trigger = selector.get_trigger_for_page(page, html)

        assert trigger is None


class TestJsSelectorPriority:
    """Tests for heuristic priority order."""

    @pytest.mark.asyncio
    async def test_missing_selectors_highest_priority(self) -> None:
        """Missing selectors should take priority over other triggers."""
        from semrush_workers.crawl.js_selector import JsSelector

        # Page has thin content AND missing selectors
        page = MockCrawlPage(text_length=50, word_count=10)
        settings = MockJsSelectorSettings(required_selectors=["h1"])
        selector = JsSelector(settings=settings)

        html = "<html><body><div></div></body></html>"
        trigger = selector.get_trigger_for_page(page, html)

        # Missing selectors should be the trigger, not thin_dom
        assert trigger == "missing_selectors"

    @pytest.mark.asyncio
    async def test_thin_dom_over_spa_shell(self) -> None:
        """Thin DOM should take priority over SPA shell detection."""
        from semrush_workers.crawl.js_selector import JsSelector

        # Page has thin content AND SPA markers
        page = MockCrawlPage(
            text_length=50,
            word_count=10,
            scripts=["app.abc123.js"],
        )
        settings = MockJsSelectorSettings()
        selector = JsSelector(settings=settings)

        html = """
        <html><body>
            <div id="root"></div>
            <script src="app.abc123.js"></script>
        </body></html>
        """
        trigger = selector.get_trigger_for_page(page, html)

        # Thin DOM should be the trigger, not SPA shell
        assert trigger == "thin_dom"


class TestJsSelectorBudget:
    """Tests for max_rendered_pages budget enforcement."""

    @pytest.mark.asyncio
    async def test_respects_max_rendered_pages(self) -> None:
        """Should not select more pages than budget allows."""
        from semrush_workers.crawl.js_selector import JsSelector

        settings = MockJsSelectorSettings(max_rendered_pages=2)
        selector = JsSelector(settings=settings)

        # Create 5 pages that all need rendering
        pages = []
        htmls = []
        for i in range(5):
            page = MockCrawlPage(
                id=uuid.uuid4(),
                url=f"https://example.com/page{i}",
                text_length=50,
                word_count=10,
            )
            pages.append(page)
            htmls.append("<html><body><div></div></body></html>")

        candidates = selector.select_candidates(pages, htmls)

        # Should only return 2 candidates (budget limit)
        assert len(candidates) == 2

    @pytest.mark.asyncio
    async def test_returns_all_when_under_budget(self) -> None:
        """Should return all candidates when under budget."""
        from semrush_workers.crawl.js_selector import JsSelector

        settings = MockJsSelectorSettings(max_rendered_pages=10)
        selector = JsSelector(settings=settings)

        # Create 3 pages that need rendering
        pages = []
        htmls = []
        for i in range(3):
            page = MockCrawlPage(
                id=uuid.uuid4(),
                url=f"https://example.com/page{i}",
                text_length=50,
                word_count=10,
            )
            pages.append(page)
            htmls.append("<html><body><div></div></body></html>")

        candidates = selector.select_candidates(pages, htmls)

        # Should return all 3 candidates
        assert len(candidates) == 3


class TestJsSelectorFiltering:
    """Tests for page filtering."""

    @pytest.mark.asyncio
    async def test_skips_already_rendered_pages(self) -> None:
        """Should not select pages that were already rendered."""
        from semrush_workers.crawl.js_selector import JsSelector

        settings = MockJsSelectorSettings()
        selector = JsSelector(settings=settings)

        # Create pages - one already rendered
        pages = [
            MockCrawlPage(
                id=uuid.uuid4(),
                was_rendered=True,
                text_length=50,
                word_count=10,
            ),
            MockCrawlPage(
                id=uuid.uuid4(),
                was_rendered=False,
                text_length=50,
                word_count=10,
            ),
        ]
        htmls = [
            "<html><body><div></div></body></html>",
            "<html><body><div></div></body></html>",
        ]

        candidates = selector.select_candidates(pages, htmls)

        # Should only return the unrendered page
        assert len(candidates) == 1
        assert candidates[0].page_id == pages[1].id

    @pytest.mark.asyncio
    async def test_skips_pages_not_needing_rendering(self) -> None:
        """Should not select pages that don't need rendering."""
        from semrush_workers.crawl.js_selector import JsSelector

        settings = MockJsSelectorSettings()
        selector = JsSelector(settings=settings)

        pages = [
            MockCrawlPage(
                id=uuid.uuid4(),
                text_length=50,  # Thin - needs rendering
                word_count=10,
            ),
            MockCrawlPage(
                id=uuid.uuid4(),
                text_length=500,  # Normal - no rendering needed
                word_count=100,
            ),
        ]
        htmls = [
            "<html><body><div></div></body></html>",
            "<html><body><h1>Title</h1><p>Content</p></body></html>",
        ]

        candidates = selector.select_candidates(pages, htmls)

        # Should only return the thin page
        assert len(candidates) == 1
        assert candidates[0].page_id == pages[0].id


class TestJsSelectorCandidateResult:
    """Tests for candidate result details."""

    @pytest.mark.asyncio
    async def test_candidate_includes_page_id(self) -> None:
        """Candidate result should include page ID."""
        from semrush_workers.crawl.js_selector import JsSelector

        page_id = uuid.uuid4()
        page = MockCrawlPage(id=page_id, text_length=50, word_count=10)
        settings = MockJsSelectorSettings()
        selector = JsSelector(settings=settings)

        candidates = selector.select_candidates(
            [page],
            ["<html><body></body></html>"],
        )

        assert len(candidates) == 1
        assert candidates[0].page_id == page_id

    @pytest.mark.asyncio
    async def test_candidate_includes_url(self) -> None:
        """Candidate result should include URL."""
        from semrush_workers.crawl.js_selector import JsSelector

        page = MockCrawlPage(
            url="https://example.com/test",
            text_length=50,
            word_count=10,
        )
        settings = MockJsSelectorSettings()
        selector = JsSelector(settings=settings)

        candidates = selector.select_candidates(
            [page],
            ["<html><body></body></html>"],
        )

        assert len(candidates) == 1
        assert candidates[0].url == "https://example.com/test"

    @pytest.mark.asyncio
    async def test_candidate_includes_trigger_reason(self) -> None:
        """Candidate result should include trigger reason."""
        from semrush_workers.crawl.js_selector import JsSelector

        page = MockCrawlPage(text_length=50, word_count=10)
        settings = MockJsSelectorSettings()
        selector = JsSelector(settings=settings)

        candidates = selector.select_candidates(
            [page],
            ["<html><body></body></html>"],
        )

        assert len(candidates) == 1
        assert candidates[0].trigger == "thin_dom"
