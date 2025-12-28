"""
Tests for Playwright renderer.

TDD tests covering:
- Chromium browser rendering
- Timeout handling (max_render_time_ms)
- Concurrency limiting (concurrency_js)
- Rendered HTML capture
- Error handling
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest


@dataclass
class MockRendererSettings:
    """Mock settings for renderer testing."""

    max_render_time_ms: int = 15000
    concurrency_js: int = 2


class TestRenderedResult:
    """Tests for RenderedResult dataclass."""

    def test_create_success_result(self) -> None:
        """Can create a successful render result."""
        from semrush_workers.crawl.renderer import RenderedResult

        result = RenderedResult(
            url="https://example.com",
            html="<html><body>Rendered</body></html>",
            success=True,
            error=None,
        )
        assert result.url == "https://example.com"
        assert result.html == "<html><body>Rendered</body></html>"
        assert result.success is True
        assert result.error is None

    def test_create_error_result(self) -> None:
        """Can create an error render result."""
        from semrush_workers.crawl.renderer import RenderedResult

        result = RenderedResult(
            url="https://example.com",
            html=None,
            success=False,
            error="Timeout error",
        )
        assert result.url == "https://example.com"
        assert result.html is None
        assert result.success is False
        assert result.error == "Timeout error"

    def test_render_time_default(self) -> None:
        """Render time should default to 0."""
        from semrush_workers.crawl.renderer import RenderedResult

        result = RenderedResult(
            url="https://example.com",
            html="<html></html>",
            success=True,
        )
        assert result.render_time_ms == 0.0


class TestRendererBasics:
    """Basic renderer tests."""

    def test_create_renderer(self) -> None:
        """Can create a renderer instance."""
        from semrush_workers.crawl.renderer import Renderer

        renderer = Renderer()
        assert renderer is not None

    def test_renderer_with_settings(self) -> None:
        """Can create renderer with custom settings."""
        from semrush_workers.crawl.renderer import Renderer

        settings = MockRendererSettings(max_render_time_ms=10000, concurrency_js=4)
        renderer = Renderer(settings=settings)
        assert renderer.timeout_ms == 10000
        assert renderer.concurrency == 4

    def test_default_timeout(self) -> None:
        """Default timeout should be 15000ms."""
        from semrush_workers.crawl.renderer import Renderer

        renderer = Renderer()
        assert renderer.timeout_ms == 15000

    def test_default_concurrency(self) -> None:
        """Default concurrency should be 2."""
        from semrush_workers.crawl.renderer import Renderer

        renderer = Renderer()
        assert renderer.concurrency == 2


class TestRendererConcurrency:
    """Tests for concurrency limiting."""

    def test_creates_semaphore_with_correct_value(self) -> None:
        """Renderer should create semaphore with concurrency limit."""
        from semrush_workers.crawl.renderer import Renderer

        settings = MockRendererSettings(concurrency_js=3)
        renderer = Renderer(settings=settings)

        # Verify semaphore is created with correct value
        assert renderer._semaphore._value == 3


class TestRendererResourceManagement:
    """Tests for resource management."""

    @pytest.mark.asyncio
    async def test_close_releases_resources(self) -> None:
        """Close should release browser resources without error."""
        from semrush_workers.crawl.renderer import Renderer

        renderer = Renderer()
        # Should not raise even if not initialized
        await renderer.close()
        assert renderer._browser is None
        assert renderer._playwright is None

    @pytest.mark.asyncio
    async def test_close_can_be_called_multiple_times(self) -> None:
        """Close should be idempotent."""
        from semrush_workers.crawl.renderer import Renderer

        renderer = Renderer()
        await renderer.close()
        await renderer.close()  # Should not raise
        assert renderer._browser is None


class TestRendererBatchInterface:
    """Tests for batch rendering interface."""

    @pytest.mark.asyncio
    async def test_render_batch_returns_list(self) -> None:
        """render_batch should return a list of results."""
        from semrush_workers.crawl.renderer import RenderedResult, Renderer

        # We'll mock the render method to avoid actual browser operations
        renderer = Renderer()

        async def mock_render(url: str) -> RenderedResult:
            return RenderedResult(
                url=url,
                html=f"<html>{url}</html>",
                success=True,
            )

        renderer.render = mock_render  # type: ignore

        urls = ["https://example.com/1", "https://example.com/2"]
        results = await renderer.render_batch(urls)

        assert len(results) == 2
        assert results[0].url == "https://example.com/1"
        assert results[1].url == "https://example.com/2"

    @pytest.mark.asyncio
    async def test_render_batch_preserves_order(self) -> None:
        """render_batch should preserve URL order in results."""
        from semrush_workers.crawl.renderer import RenderedResult, Renderer

        renderer = Renderer()

        call_order = []

        async def mock_render(url: str) -> RenderedResult:
            call_order.append(url)
            # Add varying delays to test ordering
            await asyncio.sleep(0.01)
            return RenderedResult(url=url, html=url, success=True)

        renderer.render = mock_render  # type: ignore

        urls = [f"https://example.com/{i}" for i in range(5)]
        results = await renderer.render_batch(urls)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.url == f"https://example.com/{i}"


class TestRendererErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_render_handles_exceptions_gracefully(self) -> None:
        """Render should catch exceptions and return error result."""
        from semrush_workers.crawl.renderer import Renderer

        # Mock async_playwright to raise an exception
        with patch(
            "semrush_workers.crawl.renderer.async_playwright"
        ) as mock_playwright:
            mock_playwright.return_value.start = AsyncMock(
                side_effect=Exception("Connection failed")
            )

            renderer = Renderer()
            result = await renderer.render("https://example.com")

            assert result.success is False
            assert result.html is None
            assert "Connection failed" in result.error

    @pytest.mark.asyncio
    async def test_render_returns_url_even_on_failure(self) -> None:
        """Failed render should still include the attempted URL."""
        from semrush_workers.crawl.renderer import Renderer

        with patch(
            "semrush_workers.crawl.renderer.async_playwright"
        ) as mock_playwright:
            mock_playwright.return_value.start = AsyncMock(
                side_effect=Exception("Failed")
            )

            renderer = Renderer()
            result = await renderer.render("https://test.example.com/page")

            assert result.url == "https://test.example.com/page"
