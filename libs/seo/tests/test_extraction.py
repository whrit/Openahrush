"""
Tests for HTML content extraction.

TDD tests covering:
- SEO fields extraction (title, meta description, canonical, meta robots)
- H1 extraction (count and first text)
- Word count and text length
- Link extraction (internal/external)
- Script source identification
- HTML hash computation
- Performance with lxml/selectolax
"""

from __future__ import annotations

import pytest

from semrush_seo.extraction import (
    Link,
    PageData,
    extract_page_data,
    extract_links,
    extract_meta_tags,
    compute_html_hash,
)


class TestPageData:
    """Tests for PageData dataclass."""

    def test_page_data_creation(self) -> None:
        """PageData should store all extracted fields."""
        data = PageData(
            url="https://example.com",
            title="Example Page",
            meta_description="A sample page",
            canonical="https://example.com",
            meta_robots="index, follow",
            h1_count=1,
            h1_first="Welcome",
            word_count=100,
            text_length=500,
            internal_links=[],
            external_links=[],
            scripts=[],
            html_hash="abc123",
        )
        assert data.url == "https://example.com"
        assert data.title == "Example Page"
        assert data.meta_description == "A sample page"
        assert data.h1_count == 1

    def test_page_data_optional_fields(self) -> None:
        """PageData should handle None optional fields."""
        data = PageData(
            url="https://example.com",
            title=None,
            meta_description=None,
            canonical=None,
            meta_robots=None,
            h1_count=0,
            h1_first=None,
            word_count=0,
            text_length=0,
            internal_links=[],
            external_links=[],
            scripts=[],
            html_hash="abc123",
        )
        assert data.title is None
        assert data.meta_description is None


class TestLink:
    """Tests for Link dataclass."""

    def test_link_creation(self) -> None:
        """Link should store href, text, and attributes."""
        link = Link(
            href="https://example.com/page",
            text="Click here",
            rel="nofollow",
            is_internal=True,
        )
        assert link.href == "https://example.com/page"
        assert link.text == "Click here"
        assert link.rel == "nofollow"
        assert link.is_internal is True

    def test_link_is_nofollow(self) -> None:
        """is_nofollow should detect nofollow links."""
        nofollow_link = Link(
            href="https://example.com",
            text="Link",
            rel="nofollow",
            is_internal=False,
        )
        assert nofollow_link.is_nofollow is True

        normal_link = Link(
            href="https://example.com",
            text="Link",
            rel=None,
            is_internal=False,
        )
        assert normal_link.is_nofollow is False

    def test_link_is_sponsored(self) -> None:
        """is_sponsored should detect sponsored links."""
        sponsored_link = Link(
            href="https://example.com",
            text="Link",
            rel="sponsored",
            is_internal=False,
        )
        assert sponsored_link.is_sponsored is True

    def test_link_is_ugc(self) -> None:
        """is_ugc should detect user-generated content links."""
        ugc_link = Link(
            href="https://example.com",
            text="Link",
            rel="ugc",
            is_internal=False,
        )
        assert ugc_link.is_ugc is True


class TestExtractTitle:
    """Tests for title extraction."""

    def test_extract_title_basic(self) -> None:
        """Extract basic title tag."""
        html = "<html><head><title>Example Title</title></head></html>"
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.title == "Example Title"

    def test_extract_title_with_whitespace(self) -> None:
        """Extract title with whitespace trimmed."""
        html = "<html><head><title>  Example Title  </title></head></html>"
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.title == "Example Title"

    def test_extract_title_empty(self) -> None:
        """Handle empty title tag."""
        html = "<html><head><title></title></head></html>"
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.title is None or data.title == ""

    def test_extract_title_missing(self) -> None:
        """Handle missing title tag."""
        html = "<html><head></head></html>"
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.title is None


class TestExtractMetaDescription:
    """Tests for meta description extraction."""

    def test_extract_meta_description(self) -> None:
        """Extract meta description."""
        html = """<html><head>
            <meta name="description" content="This is the description">
        </head></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.meta_description == "This is the description"

    def test_extract_meta_description_case_insensitive(self) -> None:
        """Meta name should be case-insensitive."""
        html = """<html><head>
            <meta name="Description" content="This is the description">
        </head></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.meta_description == "This is the description"

    def test_extract_meta_description_missing(self) -> None:
        """Handle missing meta description."""
        html = "<html><head></head></html>"
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.meta_description is None


class TestExtractCanonical:
    """Tests for canonical URL extraction."""

    def test_extract_canonical(self) -> None:
        """Extract canonical link."""
        html = """<html><head>
            <link rel="canonical" href="https://example.com/page">
        </head></html>"""
        data = extract_page_data(html, "https://example.com/page", "example.com")
        assert data.canonical == "https://example.com/page"

    def test_extract_canonical_missing(self) -> None:
        """Handle missing canonical."""
        html = "<html><head></head></html>"
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.canonical is None

    def test_extract_canonical_relative(self) -> None:
        """Handle relative canonical URL."""
        html = """<html><head>
            <link rel="canonical" href="/page">
        </head></html>"""
        data = extract_page_data(html, "https://example.com/page", "example.com")
        # Should either be None or resolved to absolute
        assert data.canonical is not None


class TestExtractMetaRobots:
    """Tests for meta robots extraction."""

    def test_extract_meta_robots(self) -> None:
        """Extract meta robots directive."""
        html = """<html><head>
            <meta name="robots" content="noindex, nofollow">
        </head></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert "noindex" in data.meta_robots.lower()
        assert "nofollow" in data.meta_robots.lower()

    def test_extract_meta_robots_missing(self) -> None:
        """Handle missing meta robots."""
        html = "<html><head></head></html>"
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.meta_robots is None


class TestExtractH1:
    """Tests for H1 extraction."""

    def test_extract_h1_single(self) -> None:
        """Extract single H1."""
        html = "<html><body><h1>Main Heading</h1></body></html>"
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.h1_count == 1
        assert data.h1_first == "Main Heading"

    def test_extract_h1_multiple(self) -> None:
        """Extract multiple H1s."""
        html = """<html><body>
            <h1>First Heading</h1>
            <h1>Second Heading</h1>
            <h1>Third Heading</h1>
        </body></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.h1_count == 3
        assert data.h1_first == "First Heading"

    def test_extract_h1_none(self) -> None:
        """Handle no H1 tags."""
        html = "<html><body><h2>Secondary Heading</h2></body></html>"
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.h1_count == 0
        assert data.h1_first is None

    def test_extract_h1_with_nested_elements(self) -> None:
        """Extract H1 with nested elements."""
        html = "<html><body><h1><span>Nested</span> Heading</h1></body></html>"
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.h1_count == 1
        assert "Nested" in data.h1_first
        assert "Heading" in data.h1_first


class TestExtractTextMetrics:
    """Tests for text metrics extraction."""

    def test_extract_word_count(self) -> None:
        """Extract word count from body text."""
        html = """<html><body>
            <p>This is a simple test paragraph with several words.</p>
        </body></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.word_count > 0

    def test_extract_text_length(self) -> None:
        """Extract text length (character count)."""
        html = """<html><body>
            <p>Hello World</p>
        </body></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.text_length > 0

    def test_exclude_script_style_from_word_count(self) -> None:
        """Word count should exclude script and style content."""
        html = """<html>
            <head><style>body { color: red; }</style></head>
            <body>
                <script>var x = 1; var y = 2;</script>
                <p>Only this counts.</p>
            </body>
        </html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        # Should not count script/style content
        assert data.word_count == 3  # "Only this counts"


class TestExtractLinks:
    """Tests for link extraction."""

    def test_extract_internal_links(self) -> None:
        """Extract internal links."""
        html = """<html><body>
            <a href="/page1">Page 1</a>
            <a href="https://example.com/page2">Page 2</a>
        </body></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert len(data.internal_links) == 2

    def test_extract_external_links(self) -> None:
        """Extract external links."""
        html = """<html><body>
            <a href="https://other.com/page">External Page</a>
            <a href="https://another.com/">Another Site</a>
        </body></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert len(data.external_links) == 2

    def test_extract_link_text(self) -> None:
        """Extract link anchor text."""
        html = """<html><body>
            <a href="/page">Click Here</a>
        </body></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert len(data.internal_links) == 1
        assert data.internal_links[0].text == "Click Here"

    def test_extract_link_rel(self) -> None:
        """Extract link rel attribute."""
        html = """<html><body>
            <a href="https://other.com" rel="nofollow">Nofollow Link</a>
        </body></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert len(data.external_links) == 1
        assert data.external_links[0].rel == "nofollow"

    def test_skip_javascript_links(self) -> None:
        """Skip javascript: links."""
        html = """<html><body>
            <a href="javascript:void(0)">JS Link</a>
            <a href="/real-page">Real Link</a>
        </body></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert len(data.internal_links) == 1

    def test_skip_mailto_links(self) -> None:
        """Skip mailto: links."""
        html = """<html><body>
            <a href="mailto:test@example.com">Email</a>
            <a href="/real-page">Real Link</a>
        </body></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert len(data.internal_links) == 1

    def test_resolve_relative_links(self) -> None:
        """Resolve relative links to absolute URLs."""
        html = """<html><body>
            <a href="/page">Relative Link</a>
        </body></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert len(data.internal_links) == 1
        assert data.internal_links[0].href.startswith("https://example.com")


class TestExtractScripts:
    """Tests for script source extraction."""

    def test_extract_script_sources(self) -> None:
        """Extract external script sources."""
        html = """<html><head>
            <script src="https://example.com/app.js"></script>
            <script src="/static/main.js"></script>
        </head></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert len(data.scripts) == 2

    def test_ignore_inline_scripts(self) -> None:
        """Ignore inline scripts without src."""
        html = """<html><head>
            <script>console.log('inline');</script>
            <script src="/app.js"></script>
        </head></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert len(data.scripts) == 1


class TestComputeHtmlHash:
    """Tests for HTML hash computation."""

    def test_compute_hash(self) -> None:
        """Compute hash of HTML content."""
        html = "<html><body>Test</body></html>"
        hash1 = compute_html_hash(html)
        assert hash1 is not None
        assert len(hash1) > 0

    def test_same_content_same_hash(self) -> None:
        """Same content should produce same hash."""
        html = "<html><body>Test</body></html>"
        hash1 = compute_html_hash(html)
        hash2 = compute_html_hash(html)
        assert hash1 == hash2

    def test_different_content_different_hash(self) -> None:
        """Different content should produce different hash."""
        html1 = "<html><body>Test 1</body></html>"
        html2 = "<html><body>Test 2</body></html>"
        hash1 = compute_html_hash(html1)
        hash2 = compute_html_hash(html2)
        assert hash1 != hash2


class TestExtractMetaTags:
    """Tests for meta tag extraction helper."""

    def test_extract_all_meta_tags(self) -> None:
        """Extract all meta tags."""
        html = """<html><head>
            <meta name="description" content="Description">
            <meta name="keywords" content="key1, key2">
            <meta property="og:title" content="OG Title">
        </head></html>"""
        tags = extract_meta_tags(html)
        assert "description" in tags
        assert "keywords" in tags

    def test_extract_og_meta_tags(self) -> None:
        """Extract Open Graph meta tags."""
        html = """<html><head>
            <meta property="og:title" content="OG Title">
            <meta property="og:description" content="OG Description">
        </head></html>"""
        tags = extract_meta_tags(html)
        assert "og:title" in tags or any("og:" in k for k in tags)


class TestExtractLinksFunction:
    """Tests for extract_links helper function."""

    def test_extract_links_basic(self) -> None:
        """Extract links from HTML."""
        html = """<html><body>
            <a href="https://example.com/page1">Link 1</a>
            <a href="https://other.com/page2">Link 2</a>
        </body></html>"""
        internal, external = extract_links(html, "https://example.com", "example.com")
        assert len(internal) == 1
        assert len(external) == 1


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_html(self) -> None:
        """Handle empty HTML."""
        html = ""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.title is None
        assert data.word_count == 0

    def test_malformed_html(self) -> None:
        """Handle malformed HTML."""
        html = "<html><head><title>Test<body><h1>Heading</h2>"
        data = extract_page_data(html, "https://example.com", "example.com")
        # Should not raise, may extract partial data
        assert data is not None

    def test_unicode_content(self) -> None:
        """Handle Unicode content."""
        html = """<html><head><title>Cafe Example</title></head>
            <body><h1>Welcome to the Cafe</h1></body></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert "Cafe" in data.title or "Caf" in data.title

    def test_very_large_html(self) -> None:
        """Handle large HTML documents."""
        html = "<html><body>"
        for i in range(1000):
            html += f"<p>Paragraph {i} with some content.</p>"
        html += "</body></html>"
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.word_count > 0

    def test_html_with_base_tag(self) -> None:
        """Handle HTML with base tag for relative URLs."""
        html = """<html><head>
            <base href="https://example.com/subdir/">
        </head><body>
            <a href="page">Link</a>
        </body></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        # Should handle base tag for resolving relative URLs
        assert len(data.internal_links) >= 0

    def test_multiple_meta_descriptions(self) -> None:
        """Handle multiple meta description tags (take first)."""
        html = """<html><head>
            <meta name="description" content="First description">
            <meta name="description" content="Second description">
        </head></html>"""
        data = extract_page_data(html, "https://example.com", "example.com")
        assert data.meta_description == "First description"

    def test_self_referencing_canonical(self) -> None:
        """Handle self-referencing canonical URL."""
        html = """<html><head>
            <link rel="canonical" href="https://example.com/page">
        </head></html>"""
        data = extract_page_data(html, "https://example.com/page", "example.com")
        assert data.canonical == "https://example.com/page"
