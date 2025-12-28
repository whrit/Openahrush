"""
Tests for sitemap parser.

TDD tests covering:
- Parsing sitemap.xml files
- Parsing sitemap index files
- Handling gzip-compressed sitemaps
- Extracting URLs with lastmod/priority
- Respecting use_sitemaps setting
"""

from __future__ import annotations

import gzip
from unittest.mock import AsyncMock, patch

import pytest

from semrush_seo.sitemap import (
    SitemapEntry,
    SitemapParser,
    SitemapSettings,
    parse_sitemap_xml,
    parse_sitemap_index,
)


class TestSitemapSettings:
    """Tests for SitemapSettings configuration."""

    def test_default_settings(self) -> None:
        """Default settings should have sensible values."""
        settings = SitemapSettings()
        assert settings.use_sitemaps is True
        assert settings.max_urls == 50000
        assert settings.timeout_seconds == 30

    def test_custom_settings(self) -> None:
        """Custom settings should override defaults."""
        settings = SitemapSettings(
            use_sitemaps=False,
            max_urls=10000,
            timeout_seconds=60,
        )
        assert settings.use_sitemaps is False
        assert settings.max_urls == 10000
        assert settings.timeout_seconds == 60


class TestSitemapEntry:
    """Tests for SitemapEntry dataclass."""

    def test_entry_with_url_only(self) -> None:
        """Entry should work with URL only."""
        entry = SitemapEntry(url="https://example.com/page")
        assert entry.url == "https://example.com/page"
        assert entry.lastmod is None
        assert entry.priority is None
        assert entry.changefreq is None

    def test_entry_with_all_fields(self) -> None:
        """Entry should store all optional fields."""
        entry = SitemapEntry(
            url="https://example.com/page",
            lastmod="2024-01-15",
            priority=0.8,
            changefreq="weekly",
        )
        assert entry.url == "https://example.com/page"
        assert entry.lastmod == "2024-01-15"
        assert entry.priority == 0.8
        assert entry.changefreq == "weekly"


class TestParseSitemapXml:
    """Tests for parsing sitemap XML."""

    def test_parse_simple_sitemap(self) -> None:
        """Parse a simple sitemap with one URL."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
  </url>
</urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 1
        assert entries[0].url == "https://example.com/page1"

    def test_parse_sitemap_multiple_urls(self) -> None:
        """Parse sitemap with multiple URLs."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
  </url>
  <url>
    <loc>https://example.com/page2</loc>
  </url>
  <url>
    <loc>https://example.com/page3</loc>
  </url>
</urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 3
        urls = [e.url for e in entries]
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls
        assert "https://example.com/page3" in urls

    def test_parse_sitemap_with_lastmod(self) -> None:
        """Parse sitemap with lastmod dates."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
    <lastmod>2024-01-15</lastmod>
  </url>
</urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 1
        assert entries[0].lastmod == "2024-01-15"

    def test_parse_sitemap_with_priority(self) -> None:
        """Parse sitemap with priority values."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
    <priority>0.8</priority>
  </url>
</urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 1
        assert entries[0].priority == 0.8

    def test_parse_sitemap_with_changefreq(self) -> None:
        """Parse sitemap with changefreq values."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
    <changefreq>weekly</changefreq>
  </url>
</urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 1
        assert entries[0].changefreq == "weekly"

    def test_parse_sitemap_full_entry(self) -> None:
        """Parse sitemap with all optional fields."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
    <lastmod>2024-01-15T10:30:00+00:00</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>
</urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 1
        assert entries[0].url == "https://example.com/page1"
        assert entries[0].lastmod == "2024-01-15T10:30:00+00:00"
        assert entries[0].changefreq == "monthly"
        assert entries[0].priority == 0.9

    def test_parse_empty_sitemap(self) -> None:
        """Parse empty sitemap."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
</urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 0

    def test_parse_sitemap_with_namespace_prefix(self) -> None:
        """Parse sitemap with namespace prefix."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<sm:urlset xmlns:sm="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sm:url>
    <sm:loc>https://example.com/page1</sm:loc>
  </sm:url>
</sm:urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 1
        assert entries[0].url == "https://example.com/page1"

    def test_parse_sitemap_handles_whitespace(self) -> None:
        """Parse sitemap should handle extra whitespace."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>
      https://example.com/page1
    </loc>
  </url>
</urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 1
        assert entries[0].url == "https://example.com/page1"


class TestParseSitemapIndex:
    """Tests for parsing sitemap index files."""

    def test_parse_sitemap_index(self) -> None:
        """Parse sitemap index file."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap1.xml</loc>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap2.xml</loc>
  </sitemap>
</sitemapindex>"""
        urls = parse_sitemap_index(xml)
        assert len(urls) == 2
        assert "https://example.com/sitemap1.xml" in urls
        assert "https://example.com/sitemap2.xml" in urls

    def test_parse_sitemap_index_with_lastmod(self) -> None:
        """Parse sitemap index with lastmod dates."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap1.xml</loc>
    <lastmod>2024-01-15</lastmod>
  </sitemap>
</sitemapindex>"""
        urls = parse_sitemap_index(xml)
        assert len(urls) == 1
        assert "https://example.com/sitemap1.xml" in urls

    def test_parse_empty_sitemap_index(self) -> None:
        """Parse empty sitemap index."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
</sitemapindex>"""
        urls = parse_sitemap_index(xml)
        assert len(urls) == 0


class TestSitemapParser:
    """Tests for SitemapParser class."""

    @pytest.mark.asyncio
    async def test_parser_disabled_returns_empty(self) -> None:
        """Parser should return empty list when disabled."""
        settings = SitemapSettings(use_sitemaps=False)
        parser = SitemapParser(settings=settings)

        entries = await parser.parse("https://example.com/sitemap.xml")
        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_parser_fetches_and_parses_sitemap(self) -> None:
        """Parser should fetch and parse sitemap."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
  </url>
</urlset>"""
        with patch("semrush_seo.sitemap.fetch_sitemap") as mock_fetch:
            mock_fetch.return_value = xml.encode("utf-8")

            parser = SitemapParser()
            entries = await parser.parse("https://example.com/sitemap.xml")

            assert len(entries) == 1
            assert entries[0].url == "https://example.com/page1"

    @pytest.mark.asyncio
    async def test_parser_handles_gzip_sitemap(self) -> None:
        """Parser should decompress gzip sitemaps."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
  </url>
</urlset>"""
        compressed = gzip.compress(xml.encode("utf-8"))

        with patch("semrush_seo.sitemap.fetch_sitemap") as mock_fetch:
            mock_fetch.return_value = compressed

            parser = SitemapParser()
            entries = await parser.parse("https://example.com/sitemap.xml.gz")

            assert len(entries) == 1
            assert entries[0].url == "https://example.com/page1"

    @pytest.mark.asyncio
    async def test_parser_follows_sitemap_index(self) -> None:
        """Parser should follow sitemap index to child sitemaps."""
        index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap1.xml</loc>
  </sitemap>
</sitemapindex>"""
        child_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
  </url>
</urlset>"""

        call_count = [0]

        async def mock_fetch(url: str, timeout: float = 30.0) -> bytes:
            call_count[0] += 1
            if "index" in url or call_count[0] == 1:
                return index_xml.encode("utf-8")
            return child_xml.encode("utf-8")

        with patch("semrush_seo.sitemap.fetch_sitemap", new=mock_fetch):
            parser = SitemapParser()
            entries = await parser.parse("https://example.com/sitemap-index.xml")

            assert len(entries) >= 1

    @pytest.mark.asyncio
    async def test_parser_respects_max_urls(self) -> None:
        """Parser should stop at max_urls limit."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">"""
        for i in range(100):
            xml += f"<url><loc>https://example.com/page{i}</loc></url>"
        xml += "</urlset>"

        with patch("semrush_seo.sitemap.fetch_sitemap") as mock_fetch:
            mock_fetch.return_value = xml.encode("utf-8")

            settings = SitemapSettings(max_urls=10)
            parser = SitemapParser(settings=settings)
            entries = await parser.parse("https://example.com/sitemap.xml")

            assert len(entries) == 10

    @pytest.mark.asyncio
    async def test_parser_handles_fetch_error(self) -> None:
        """Parser should handle fetch errors gracefully."""
        with patch("semrush_seo.sitemap.fetch_sitemap") as mock_fetch:
            mock_fetch.side_effect = Exception("Network error")

            parser = SitemapParser()
            entries = await parser.parse("https://example.com/sitemap.xml")

            assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_parser_handles_malformed_xml(self) -> None:
        """Parser should handle malformed XML gracefully."""
        xml = "This is not valid XML <broken>"

        with patch("semrush_seo.sitemap.fetch_sitemap") as mock_fetch:
            mock_fetch.return_value = xml.encode("utf-8")

            parser = SitemapParser()
            entries = await parser.parse("https://example.com/sitemap.xml")

            assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_parser_deduplicates_urls(self) -> None:
        """Parser should deduplicate URLs from multiple sitemaps."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
  </url>
  <url>
    <loc>https://example.com/page1</loc>
  </url>
</urlset>"""

        with patch("semrush_seo.sitemap.fetch_sitemap") as mock_fetch:
            mock_fetch.return_value = xml.encode("utf-8")

            parser = SitemapParser()
            entries = await parser.parse("https://example.com/sitemap.xml")

            assert len(entries) == 1


class TestSitemapEdgeCases:
    """Tests for edge cases."""

    def test_parse_sitemap_with_html_entities(self) -> None:
        """Parser should handle HTML entities in URLs."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page?a=1&amp;b=2</loc>
  </url>
</urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 1
        assert "a=1&b=2" in entries[0].url or "a=1&amp;b=2" in entries[0].url

    def test_parse_sitemap_unicode_urls(self) -> None:
        """Parser should handle Unicode URLs."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/cafe</loc>
  </url>
</urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 1

    def test_parse_sitemap_invalid_priority(self) -> None:
        """Parser should handle invalid priority values."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page1</loc>
    <priority>invalid</priority>
  </url>
</urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 1
        assert entries[0].priority is None  # Should default to None on invalid

    def test_parse_sitemap_cdata(self) -> None:
        """Parser should handle CDATA sections."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc><![CDATA[https://example.com/page1]]></loc>
  </url>
</urlset>"""
        entries = parse_sitemap_xml(xml)
        assert len(entries) == 1
        assert entries[0].url == "https://example.com/page1"

    def test_detect_sitemap_vs_index(self) -> None:
        """Parser should detect sitemap vs sitemap index."""
        sitemap_xml = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com</loc></url>
</urlset>"""

        index_xml = """<?xml version="1.0"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>
</sitemapindex>"""

        # parse_sitemap_xml should return URLs from urlset
        entries = parse_sitemap_xml(sitemap_xml)
        assert len(entries) == 1

        # parse_sitemap_index should return sitemap URLs from sitemapindex
        urls = parse_sitemap_index(index_xml)
        assert len(urls) == 1
        assert "sitemap1.xml" in urls[0]
