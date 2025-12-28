"""
Tests for render orchestrator.

TDD tests covering:
- Loading candidate pages up to budget
- Rendering pages concurrently with bounded semaphore
- Re-extracting page data from rendered HTML
- Storing rendered HTML to MinIO (mocked)
- Updating crawl_page records with rendered data
- Updating crawl_run status through lifecycle
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import pytest


@dataclass
class MockCrawlPage:
    """Mock crawl page for testing."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    url: str = "https://example.com/page"
    html_artifact_key: str = "artifacts/page.html"
    was_rendered: bool = False
    render_trigger: str | None = None
    text_length: int = 50
    word_count: int = 10
    scripts: list[str] = field(default_factory=list)


@dataclass
class MockCrawlRun:
    """Mock crawl run for testing."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    project_id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: str = "html_complete"
    config_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class MockOrchestratorSettings:
    """Mock settings for orchestrator testing."""

    max_rendered_pages: int = 200
    max_render_time_ms: int = 15000
    concurrency_js: int = 2
    min_text_chars: int = 200
    min_word_count: int = 50
    required_selectors: list[str] = field(default_factory=list)


class MockRenderedResult:
    """Mock rendered result."""

    def __init__(
        self,
        url: str,
        html: str | None = None,
        success: bool = True,
        error: str | None = None,
    ):
        self.url = url
        self.html = html
        self.success = success
        self.error = error


class TestRenderOrchestratorInit:
    """Tests for orchestrator initialization."""

    def test_create_orchestrator(self) -> None:
        """Can create an orchestrator instance."""
        from semrush_workers.crawl.render_orchestrator import RenderOrchestrator

        orchestrator = RenderOrchestrator()
        assert orchestrator is not None

    def test_orchestrator_with_settings(self) -> None:
        """Can create orchestrator with custom settings."""
        from semrush_workers.crawl.render_orchestrator import RenderOrchestrator

        settings = MockOrchestratorSettings(max_rendered_pages=50)
        orchestrator = RenderOrchestrator(settings=settings)
        assert orchestrator._settings.max_rendered_pages == 50


class TestRenderOrchestratorCandidateSelection:
    """Tests for candidate selection logic."""

    @pytest.mark.asyncio
    async def test_selects_candidates_using_heuristics(self) -> None:
        """Orchestrator should use heuristics to select candidates."""
        from semrush_workers.crawl.render_orchestrator import RenderOrchestrator

        settings = MockOrchestratorSettings()
        orchestrator = RenderOrchestrator(settings=settings)

        # Pages with thin content should be selected
        pages = [
            MockCrawlPage(text_length=50, word_count=10),  # Thin - should select
            MockCrawlPage(text_length=500, word_count=100),  # Normal - skip
        ]
        htmls = [
            "<html><body></body></html>",
            "<html><body><h1>Title</h1><p>Content</p></body></html>",
        ]

        candidates = orchestrator.select_candidates(pages, htmls)

        assert len(candidates) == 1
        assert candidates[0].page_id == pages[0].id

    @pytest.mark.asyncio
    async def test_respects_budget_limit(self) -> None:
        """Orchestrator should respect max_rendered_pages budget."""
        from semrush_workers.crawl.render_orchestrator import RenderOrchestrator

        settings = MockOrchestratorSettings(max_rendered_pages=2)
        orchestrator = RenderOrchestrator(settings=settings)

        # All pages have thin content
        pages = [MockCrawlPage(text_length=50, word_count=10) for _ in range(5)]
        htmls = ["<html><body></body></html>"] * 5

        candidates = orchestrator.select_candidates(pages, htmls)

        assert len(candidates) == 2  # Limited by budget


class TestRenderOrchestratorRendering:
    """Tests for rendering orchestration."""

    @pytest.mark.asyncio
    async def test_render_candidates_returns_results(self) -> None:
        """render_candidates should return results for all candidates."""
        from semrush_workers.crawl.render_orchestrator import (
            RenderCandidate,
            RenderOrchestrator,
        )

        orchestrator = RenderOrchestrator()

        # Mock the renderer's render_batch method
        mock_renderer = AsyncMock()
        mock_renderer.render_batch = AsyncMock(
            return_value=[
                MockRenderedResult(
                    url="https://example.com/1",
                    html="<html><body>Rendered</body></html>",
                    success=True,
                ),
                MockRenderedResult(
                    url="https://example.com/2",
                    html="<html><body>Rendered</body></html>",
                    success=True,
                ),
            ]
        )
        orchestrator._renderer = mock_renderer

        candidates = [
            RenderCandidate(
                page_id=uuid.uuid4(),
                url="https://example.com/1",
                trigger="thin_dom",
            ),
            RenderCandidate(
                page_id=uuid.uuid4(),
                url="https://example.com/2",
                trigger="spa_shell",
            ),
        ]

        results = await orchestrator.render_candidates(candidates)

        assert len(results) == 2
        mock_renderer.render_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_render_candidates_handles_failures(self) -> None:
        """render_candidates should handle render failures gracefully."""
        from semrush_workers.crawl.render_orchestrator import (
            RenderCandidate,
            RenderOrchestrator,
        )

        orchestrator = RenderOrchestrator()

        # Mock renderer that fails
        mock_renderer = AsyncMock()
        mock_renderer.render_batch = AsyncMock(
            return_value=[
                MockRenderedResult(
                    url="https://example.com",
                    html=None,
                    success=False,
                    error="Timeout",
                ),
            ]
        )
        orchestrator._renderer = mock_renderer

        candidates = [
            RenderCandidate(
                page_id=uuid.uuid4(),
                url="https://example.com/1",
                trigger="thin_dom",
            ),
        ]

        results = await orchestrator.render_candidates(candidates)

        assert len(results) == 1
        assert results[0].success is False


class TestRenderOrchestratorStorage:
    """Tests for storage operations."""

    @pytest.mark.asyncio
    async def test_store_rendered_html_calls_storage(self) -> None:
        """store_rendered_html should call the storage client."""
        from semrush_workers.crawl.render_orchestrator import RenderOrchestrator

        orchestrator = RenderOrchestrator()

        mock_storage = AsyncMock()
        mock_storage.put_object = AsyncMock(return_value="artifacts/rendered.html")
        orchestrator._storage = mock_storage

        page_id = uuid.uuid4()
        html = "<html><body>Rendered</body></html>"

        key = await orchestrator.store_rendered_html(page_id, html)

        assert key is not None
        mock_storage.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_rendered_html_generates_key(self) -> None:
        """store_rendered_html should generate artifact key."""
        from semrush_workers.crawl.render_orchestrator import RenderOrchestrator

        orchestrator = RenderOrchestrator()

        mock_storage = AsyncMock()
        mock_storage.put_object = AsyncMock(return_value="ok")
        orchestrator._storage = mock_storage

        page_id = uuid.uuid4()
        html = "<html><body>Content</body></html>"

        key = await orchestrator.store_rendered_html(page_id, html)

        assert str(page_id) in key
        assert "rendered" in key.lower()


class TestRenderOrchestratorLifecycle:
    """Tests for crawl run lifecycle updates."""

    @pytest.mark.asyncio
    async def test_updates_status_to_selecting(self) -> None:
        """Orchestrator should update status to 'selecting_js'."""
        from semrush_workers.crawl.render_orchestrator import RenderOrchestrator

        orchestrator = RenderOrchestrator()

        mock_db = AsyncMock()
        crawl_run_id = uuid.uuid4()

        await orchestrator.update_status(
            crawl_run_id, "selecting_js", db_session=mock_db
        )

        # Status update should have been called
        assert mock_db.execute.called or mock_db.commit.called

    @pytest.mark.asyncio
    async def test_updates_status_to_rendering(self) -> None:
        """Orchestrator should update status to 'rendering_js'."""
        from semrush_workers.crawl.render_orchestrator import RenderOrchestrator

        orchestrator = RenderOrchestrator()

        mock_db = AsyncMock()
        crawl_run_id = uuid.uuid4()

        await orchestrator.update_status(
            crawl_run_id, "rendering_js", db_session=mock_db
        )

        assert mock_db.execute.called or mock_db.commit.called


class TestRenderOrchestratorPageUpdate:
    """Tests for page record updates."""

    @pytest.mark.asyncio
    async def test_update_page_with_rendered_data(self) -> None:
        """update_page should store rendered data."""
        from semrush_workers.crawl.render_orchestrator import RenderOrchestrator

        orchestrator = RenderOrchestrator()

        mock_db = AsyncMock()
        page_id = uuid.uuid4()
        rendered_html = "<html><body>Rendered Content</body></html>"

        await orchestrator.update_page_with_rendered_data(
            page_id=page_id,
            rendered_html=rendered_html,
            render_trigger="thin_dom",
            db_session=mock_db,
        )

        # Database should have been updated
        assert mock_db.execute.called or mock_db.commit.called


class TestRenderOrchestratorFullFlow:
    """Integration tests for full orchestration flow."""

    @pytest.mark.asyncio
    async def test_process_run_selects_and_renders(self) -> None:
        """process_run should select candidates and render them."""
        from semrush_workers.crawl.render_orchestrator import RenderOrchestrator

        orchestrator = RenderOrchestrator()

        # Mock all components
        _mock_db = AsyncMock()
        mock_storage = AsyncMock()
        mock_storage.put_object = AsyncMock(return_value="key")
        orchestrator._storage = mock_storage

        mock_renderer = AsyncMock()
        mock_renderer.render_batch = AsyncMock(
            return_value=[
                MockRenderedResult(
                    url="https://example.com",
                    html="<html><body>Rendered</body></html>",
                    success=True,
                ),
            ]
        )
        mock_renderer.close = AsyncMock()
        orchestrator._renderer = mock_renderer

        # Create test data
        pages = [
            MockCrawlPage(text_length=50, word_count=10),
        ]
        htmls = ["<html><body></body></html>"]

        # Run the flow
        candidates = orchestrator.select_candidates(pages, htmls)
        assert len(candidates) == 1

        results = await orchestrator.render_candidates(candidates)
        assert len(results) == 1
        assert results[0].success is True
