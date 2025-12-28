"""
Playwright renderer for JavaScript-dependent pages.

Provides async rendering of pages using Chromium via Playwright,
with timeout handling, concurrency limiting, and resource management.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from playwright.async_api import async_playwright

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright

logger = logging.getLogger(__name__)


@dataclass
class RenderedResult:
    """
    Result from JavaScript rendering a page.

    Attributes:
        url: URL that was rendered.
        html: Rendered HTML content (None if failed).
        success: Whether rendering succeeded.
        error: Error message if rendering failed.
        render_time_ms: Time to render in milliseconds.
    """

    url: str
    html: str | None
    success: bool
    error: str | None = None
    render_time_ms: float = 0.0


@dataclass
class DefaultRendererSettings:
    """Default settings for the renderer."""

    max_render_time_ms: int = 15000
    concurrency_js: int = 2


class Renderer:
    """
    Playwright-based page renderer.

    Renders JavaScript-dependent pages using headless Chromium,
    with configurable timeout and concurrency limits.
    """

    def __init__(self, settings: Any | None = None) -> None:
        """
        Initialize the renderer.

        Args:
            settings: Settings object with max_render_time_ms and concurrency_js.
        """
        if settings is None:
            settings = DefaultRendererSettings()

        self.timeout_ms = getattr(settings, "max_render_time_ms", 15000)
        self.concurrency = getattr(settings, "concurrency_js", 2)
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> Renderer:
        """Async context manager entry."""
        await self._ensure_browser()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit - cleanup resources."""
        await self.close()

    async def _ensure_browser(self) -> None:
        """Ensure browser is initialized."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
            )

    async def render(self, url: str) -> RenderedResult:
        """
        Render a single page with JavaScript execution.

        Uses Chromium to navigate to the URL, wait for network idle,
        and capture the rendered HTML.

        Args:
            url: URL to render.

        Returns:
            RenderedResult with rendered HTML or error.
        """
        import time

        start_time = time.monotonic()

        async with self._semaphore:
            playwright: Playwright | None = None
            browser: Browser | None = None
            context: BrowserContext | None = None
            page: Page | None = None

            try:
                # Create fresh context for each render
                playwright = await async_playwright().start()
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Openahrush/1.0 (compatible; +https://openahrush.com/bot)",
                )
                page = await context.new_page()

                # Navigate with timeout
                await page.goto(
                    url,
                    timeout=self.timeout_ms,
                    wait_until="domcontentloaded",
                )

                # Wait for network to be idle (or timeout)
                with contextlib.suppress(Exception):
                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=min(5000, self.timeout_ms // 3),
                    )

                # Get rendered HTML
                html = await page.content()

                render_time = (time.monotonic() - start_time) * 1000

                return RenderedResult(
                    url=url,
                    html=html,
                    success=True,
                    error=None,
                    render_time_ms=render_time,
                )

            except TimeoutError:
                render_time = (time.monotonic() - start_time) * 1000
                return RenderedResult(
                    url=url,
                    html=None,
                    success=False,
                    error="Render timeout exceeded",
                    render_time_ms=render_time,
                )

            except Exception as e:
                render_time = (time.monotonic() - start_time) * 1000
                logger.warning("Render failed for %s: %s", url, e)
                return RenderedResult(
                    url=url,
                    html=None,
                    success=False,
                    error=str(e),
                    render_time_ms=render_time,
                )

            finally:
                # Clean up resources - use suppress for async cleanup
                if page is not None:
                    with contextlib.suppress(Exception):
                        await page.close()
                if context is not None:
                    with contextlib.suppress(Exception):
                        await context.close()
                if browser is not None:
                    with contextlib.suppress(Exception):
                        await browser.close()
                if playwright is not None:
                    with contextlib.suppress(Exception):
                        await playwright.stop()

    async def render_batch(self, urls: list[str]) -> list[RenderedResult]:
        """
        Render multiple pages concurrently.

        Respects concurrency limits via semaphore.

        Args:
            urls: List of URLs to render.

        Returns:
            List of RenderedResults in same order as input.
        """
        tasks = [self.render(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def close(self) -> None:
        """Close browser and release resources."""
        if self._browser:
            with contextlib.suppress(Exception):
                await self._browser.close()
            self._browser = None

        if self._playwright:
            with contextlib.suppress(Exception):
                await self._playwright.stop()
            self._playwright = None
