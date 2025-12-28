"""
Tests for JS rendering decision heuristics.

TDD tests covering:
- Thin DOM detection (low text/word count)
- SPA shell detection (framework markers)
- Missing selectors detection
- Client-side redirect detection
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MockPageData:
    """Mock page data for testing heuristics."""

    text_length: int = 500
    word_count: int = 100
    scripts: list[str] | None = None

    def __post_init__(self) -> None:
        if self.scripts is None:
            self.scripts = []


@dataclass
class MockHeuristicsSettings:
    """Mock settings for heuristics testing."""

    min_text_chars: int = 200
    min_word_count: int = 50
    required_selectors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.required_selectors is None:
            self.required_selectors = []


class TestNeedsJsThinDom:
    """Tests for thin DOM heuristic."""

    def test_returns_false_for_normal_content(self) -> None:
        """Normal content should not trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_thin_dom

        page = MockPageData(text_length=500, word_count=100)
        settings = MockHeuristicsSettings()
        result = needs_js_thin_dom(page, settings)
        assert result is False

    def test_returns_true_for_low_text_length(self) -> None:
        """Low text length should trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_thin_dom

        page = MockPageData(text_length=100, word_count=100)
        settings = MockHeuristicsSettings(min_text_chars=200)
        result = needs_js_thin_dom(page, settings)
        assert result is True

    def test_returns_true_for_low_word_count(self) -> None:
        """Low word count should trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_thin_dom

        page = MockPageData(text_length=500, word_count=30)
        settings = MockHeuristicsSettings(min_word_count=50)
        result = needs_js_thin_dom(page, settings)
        assert result is True

    def test_returns_true_when_both_low(self) -> None:
        """Both metrics low should trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_thin_dom

        page = MockPageData(text_length=50, word_count=10)
        settings = MockHeuristicsSettings()
        result = needs_js_thin_dom(page, settings)
        assert result is True

    def test_respects_custom_thresholds(self) -> None:
        """Custom thresholds should be respected."""
        from semrush_workers.crawl.heuristics import needs_js_thin_dom

        page = MockPageData(text_length=150, word_count=40)
        settings = MockHeuristicsSettings(min_text_chars=100, min_word_count=30)
        result = needs_js_thin_dom(page, settings)
        assert result is False

    def test_returns_true_for_zero_text(self) -> None:
        """Zero text should definitely trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_thin_dom

        page = MockPageData(text_length=0, word_count=0)
        settings = MockHeuristicsSettings()
        result = needs_js_thin_dom(page, settings)
        assert result is True


class TestNeedsJsSpaShell:
    """Tests for SPA shell heuristic."""

    def test_returns_false_for_normal_html(self) -> None:
        """Normal HTML should not trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_spa_shell

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Normal Page</title></head>
        <body>
            <header>Header</header>
            <main>
                <article>
                    <h1>Title</h1>
                    <p>Content paragraph with text.</p>
                </article>
            </main>
            <footer>Footer</footer>
        </body>
        </html>
        """
        page = MockPageData()
        result = needs_js_spa_shell(page, html)
        assert result is False

    def test_detects_react_root_div(self) -> None:
        """React #root div should trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_spa_shell

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>React App</title></head>
        <body>
            <div id="root"></div>
        </body>
        </html>
        """
        page = MockPageData()
        result = needs_js_spa_shell(page, html)
        assert result is True

    def test_detects_app_div(self) -> None:
        """Generic #app div should trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_spa_shell

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Vue App</title></head>
        <body>
            <div id="app"></div>
        </body>
        </html>
        """
        page = MockPageData()
        result = needs_js_spa_shell(page, html)
        assert result is True

    def test_detects_next_js_root(self) -> None:
        """Next.js __next div should trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_spa_shell

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Next.js App</title></head>
        <body>
            <div id="__next"></div>
        </body>
        </html>
        """
        page = MockPageData()
        result = needs_js_spa_shell(page, html)
        assert result is True

    def test_detects_nuxt_root(self) -> None:
        """Nuxt.js __nuxt div should trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_spa_shell

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Nuxt App</title></head>
        <body>
            <div id="__nuxt"></div>
        </body>
        </html>
        """
        page = MockPageData()
        result = needs_js_spa_shell(page, html)
        assert result is True

    def test_detects_svelte_root(self) -> None:
        """Svelte root should trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_spa_shell

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Svelte App</title></head>
        <body>
            <div id="svelte"></div>
        </body>
        </html>
        """
        page = MockPageData()
        result = needs_js_spa_shell(page, html)
        assert result is True

    def test_detects_spa_bundle_app_hash_js(self) -> None:
        """SPA bundle app.*.js should trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_spa_shell

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>App</title></head>
        <body>
            <div>Content</div>
            <script src="/static/js/app.abc123def.js"></script>
        </body>
        </html>
        """
        page = MockPageData(scripts=["/static/js/app.abc123def.js"])
        result = needs_js_spa_shell(page, html)
        assert result is True

    def test_detects_spa_bundle_main_hash_js(self) -> None:
        """SPA bundle main.*.js should trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_spa_shell

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>App</title></head>
        <body>
            <div>Content</div>
        </body>
        </html>
        """
        page = MockPageData(scripts=["/static/js/main.def456.js"])
        result = needs_js_spa_shell(page, html)
        assert result is True

    def test_detects_chunk_js_pattern(self) -> None:
        """Webpack chunk pattern should trigger JS rendering."""
        from semrush_workers.crawl.heuristics import needs_js_spa_shell

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>App</title></head>
        <body>
            <div>Content</div>
        </body>
        </html>
        """
        page = MockPageData(scripts=["chunk.vendors.js", "chunk.123.js"])
        result = needs_js_spa_shell(page, html)
        assert result is True

    def test_root_div_with_content_not_spa(self) -> None:
        """Root div with actual content should not trigger."""
        from semrush_workers.crawl.heuristics import needs_js_spa_shell

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>App</title></head>
        <body>
            <div id="root">
                <header>Navigation</header>
                <main>Real content</main>
                <footer>Footer</footer>
            </div>
        </body>
        </html>
        """
        page = MockPageData()
        result = needs_js_spa_shell(page, html)
        assert result is False

    def test_multiple_body_children_not_spa(self) -> None:
        """Multiple direct body children should not trigger SPA detection."""
        from semrush_workers.crawl.heuristics import needs_js_spa_shell

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Normal</title></head>
        <body>
            <header>Header</header>
            <div id="root">Content</div>
            <footer>Footer</footer>
        </body>
        </html>
        """
        page = MockPageData()
        result = needs_js_spa_shell(page, html)
        assert result is False


class TestNeedsJsMissingSelectors:
    """Tests for missing selectors heuristic."""

    def test_returns_false_when_no_required_selectors(self) -> None:
        """No required selectors means no trigger."""
        from semrush_workers.crawl.heuristics import needs_js_missing_selectors

        html = "<html><body><div>Content</div></body></html>"
        settings = MockHeuristicsSettings(required_selectors=[])
        result = needs_js_missing_selectors(html, settings)
        assert result is False

    def test_returns_false_when_all_selectors_found(self) -> None:
        """All required selectors present should not trigger."""
        from semrush_workers.crawl.heuristics import needs_js_missing_selectors

        html = """
        <html>
        <body>
            <h1>Title</h1>
            <main>
                <article>Content</article>
            </main>
        </body>
        </html>
        """
        settings = MockHeuristicsSettings(required_selectors=["h1", "main", "article"])
        result = needs_js_missing_selectors(html, settings)
        assert result is False

    def test_returns_true_when_selector_missing(self) -> None:
        """Missing required selector should trigger."""
        from semrush_workers.crawl.heuristics import needs_js_missing_selectors

        html = """
        <html>
        <body>
            <div>Content without h1</div>
        </body>
        </html>
        """
        settings = MockHeuristicsSettings(required_selectors=["h1"])
        result = needs_js_missing_selectors(html, settings)
        assert result is True

    def test_returns_true_when_any_selector_missing(self) -> None:
        """Any missing selector should trigger."""
        from semrush_workers.crawl.heuristics import needs_js_missing_selectors

        html = """
        <html>
        <body>
            <h1>Title</h1>
            <div>Content</div>
        </body>
        </html>
        """
        settings = MockHeuristicsSettings(required_selectors=["h1", "main", ".product-title"])
        result = needs_js_missing_selectors(html, settings)
        assert result is True

    def test_supports_class_selectors(self) -> None:
        """Class selectors should work."""
        from semrush_workers.crawl.heuristics import needs_js_missing_selectors

        html = '<html><body><div class="product-title">Product</div></body></html>'
        settings = MockHeuristicsSettings(required_selectors=[".product-title"])
        result = needs_js_missing_selectors(html, settings)
        assert result is False

    def test_supports_id_selectors(self) -> None:
        """ID selectors should work."""
        from semrush_workers.crawl.heuristics import needs_js_missing_selectors

        html = '<html><body><div id="main-content">Content</div></body></html>'
        settings = MockHeuristicsSettings(required_selectors=["#main-content"])
        result = needs_js_missing_selectors(html, settings)
        assert result is False

    def test_supports_attribute_selectors(self) -> None:
        """Attribute selectors should work."""
        from semrush_workers.crawl.heuristics import needs_js_missing_selectors

        html = '<html><body><a data-testid="nav-link">Link</a></body></html>'
        settings = MockHeuristicsSettings(required_selectors=["[data-testid]"])
        result = needs_js_missing_selectors(html, settings)
        assert result is False

    def test_supports_descendant_selectors(self) -> None:
        """Descendant selectors should work."""
        from semrush_workers.crawl.heuristics import needs_js_missing_selectors

        html = "<html><body><main><article>Content</article></main></body></html>"
        settings = MockHeuristicsSettings(required_selectors=["main article"])
        result = needs_js_missing_selectors(html, settings)
        assert result is False


class TestNeedsJsClientRedirect:
    """Tests for client-side redirect heuristic."""

    def test_returns_false_for_normal_html(self) -> None:
        """Normal HTML should not trigger."""
        from semrush_workers.crawl.heuristics import needs_js_client_redirect

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Normal Page</title></head>
        <body>
            <h1>Hello World</h1>
        </body>
        </html>
        """
        result = needs_js_client_redirect(html)
        assert result is False

    def test_detects_window_location_assignment(self) -> None:
        """window.location = should trigger."""
        from semrush_workers.crawl.heuristics import needs_js_client_redirect

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script>
                window.location = '/new-page';
            </script>
        </head>
        <body></body>
        </html>
        """
        result = needs_js_client_redirect(html)
        assert result is True

    def test_detects_window_location_href_assignment(self) -> None:
        """window.location.href = should trigger."""
        from semrush_workers.crawl.heuristics import needs_js_client_redirect

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script>
                window.location.href = 'https://example.com/redirect';
            </script>
        </head>
        <body></body>
        </html>
        """
        result = needs_js_client_redirect(html)
        assert result is True

    def test_detects_window_location_replace(self) -> None:
        """window.location.replace() should trigger."""
        from semrush_workers.crawl.heuristics import needs_js_client_redirect

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script>
                window.location.replace('/target');
            </script>
        </head>
        <body></body>
        </html>
        """
        result = needs_js_client_redirect(html)
        assert result is True

    def test_detects_meta_refresh_low_delay(self) -> None:
        """meta refresh with low delay should trigger."""
        from semrush_workers.crawl.heuristics import needs_js_client_redirect

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta http-equiv="refresh" content="0; url=/redirect">
        </head>
        <body></body>
        </html>
        """
        result = needs_js_client_redirect(html)
        assert result is True

    def test_detects_meta_refresh_short_delay(self) -> None:
        """meta refresh with short delay (under 5s) should trigger."""
        from semrush_workers.crawl.heuristics import needs_js_client_redirect

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta http-equiv="refresh" content="3; url=/redirect">
        </head>
        <body></body>
        </html>
        """
        result = needs_js_client_redirect(html)
        assert result is True

    def test_ignores_meta_refresh_long_delay(self) -> None:
        """meta refresh with long delay should not trigger."""
        from semrush_workers.crawl.heuristics import needs_js_client_redirect

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta http-equiv="refresh" content="60; url=/redirect">
        </head>
        <body></body>
        </html>
        """
        result = needs_js_client_redirect(html)
        assert result is False

    def test_detects_document_location(self) -> None:
        """document.location should also trigger."""
        from semrush_workers.crawl.heuristics import needs_js_client_redirect

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script>
                document.location = '/redirect';
            </script>
        </head>
        <body></body>
        </html>
        """
        result = needs_js_client_redirect(html)
        assert result is True

    def test_case_insensitive_meta_refresh(self) -> None:
        """meta refresh detection should be case-insensitive."""
        from semrush_workers.crawl.heuristics import needs_js_client_redirect

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <META HTTP-EQUIV="REFRESH" CONTENT="0; URL=/redirect">
        </head>
        <body></body>
        </html>
        """
        result = needs_js_client_redirect(html)
        assert result is True


class TestNeedsJsBodyMostlyScripts:
    """Tests for body mostly scripts/styles detection."""

    def test_returns_true_for_script_heavy_body(self) -> None:
        """Body with mostly scripts should trigger."""
        from semrush_workers.crawl.heuristics import needs_js_thin_dom

        # This is reflected in text_length being low
        page = MockPageData(text_length=20, word_count=5)
        settings = MockHeuristicsSettings()
        result = needs_js_thin_dom(page, settings)
        assert result is True

    def test_returns_false_for_content_rich_body(self) -> None:
        """Body with substantial content should not trigger."""
        from semrush_workers.crawl.heuristics import needs_js_thin_dom

        page = MockPageData(text_length=1000, word_count=200)
        settings = MockHeuristicsSettings()
        result = needs_js_thin_dom(page, settings)
        assert result is False
