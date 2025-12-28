"""
Sitemap parser for URL discovery.

Provides parsing of sitemap.xml files with:
- Standard sitemap.xml parsing
- Sitemap index file support
- Gzip compressed sitemap handling
- URL extraction with lastmod/priority/changefreq
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass, field
from xml.etree import ElementTree

import httpx


@dataclass
class SitemapSettings:
    """
    Configuration settings for sitemap parsing.

    Attributes:
        use_sitemaps: Whether to use sitemaps for URL discovery.
        max_urls: Maximum URLs to extract from sitemaps.
        timeout_seconds: Request timeout for fetching sitemaps.
    """

    use_sitemaps: bool = True
    max_urls: int = 50000
    timeout_seconds: int = 30


@dataclass
class SitemapEntry:
    """
    A single URL entry from a sitemap.

    Attributes:
        url: The URL from the sitemap.
        lastmod: Last modification date (if specified).
        priority: URL priority 0.0-1.0 (if specified).
        changefreq: Change frequency hint (if specified).
    """

    url: str
    lastmod: str | None = None
    priority: float | None = None
    changefreq: str | None = None


# XML namespace for sitemaps
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


async def fetch_sitemap(url: str, timeout: float = 30.0) -> bytes:
    """
    Fetch a sitemap from URL.

    Args:
        url: Sitemap URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        Raw sitemap content as bytes.

    Raises:
        Exception: If fetch fails.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def _decompress_if_gzip(content: bytes) -> bytes:
    """
    Decompress content if it's gzip compressed.

    Args:
        content: Raw content bytes.

    Returns:
        Decompressed content if gzip, otherwise original.
    """
    # Check for gzip magic bytes
    if content[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(content)
        except Exception:
            pass
    return content


def _get_text(element: ElementTree.Element | None) -> str | None:
    """Get text content from an element, handling None."""
    if element is not None and element.text:
        return element.text.strip()
    return None


def _parse_priority(value: str | None) -> float | None:
    """Parse priority value, returning None on invalid."""
    if value is None:
        return None
    try:
        priority = float(value)
        if 0.0 <= priority <= 1.0:
            return priority
        return None
    except ValueError:
        return None


def _find_with_ns(element: ElementTree.Element, tag: str) -> ElementTree.Element | None:
    """
    Find child element with namespace handling.

    Handles both namespaced and non-namespaced elements.
    """
    # Try without namespace first (more common in practice)
    result = element.find(tag)
    if result is not None:
        return result

    # Try with namespace
    result = element.find(f"sm:{tag}", SITEMAP_NS)
    if result is not None:
        return result

    # Try with inline namespace
    result = element.find(f"{{{SITEMAP_NS['sm']}}}{tag}")
    return result


def _findall_with_ns(element: ElementTree.Element, tag: str) -> list[ElementTree.Element]:
    """
    Find all child elements with namespace handling.

    Handles both namespaced and non-namespaced elements.
    """
    # Try without namespace first
    results = element.findall(tag)
    if results:
        return results

    # Try with namespace prefix
    results = element.findall(f"sm:{tag}", SITEMAP_NS)
    if results:
        return results

    # Try with inline namespace
    results = element.findall(f"{{{SITEMAP_NS['sm']}}}{tag}")
    return results


def parse_sitemap_xml(content: str | bytes) -> list[SitemapEntry]:
    """
    Parse a sitemap XML file and extract URL entries.

    Args:
        content: Sitemap XML content (string or bytes).

    Returns:
        List of SitemapEntry objects.
    """
    if isinstance(content, bytes):
        content = _decompress_if_gzip(content)
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            content = content.decode("latin-1")

    entries: list[SitemapEntry] = []

    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return entries

    # Find all <url> elements
    url_elements = _findall_with_ns(root, "url")

    for url_elem in url_elements:
        loc_elem = _find_with_ns(url_elem, "loc")
        loc = _get_text(loc_elem)

        if not loc:
            continue

        lastmod = _get_text(_find_with_ns(url_elem, "lastmod"))
        priority_str = _get_text(_find_with_ns(url_elem, "priority"))
        priority = _parse_priority(priority_str)
        changefreq = _get_text(_find_with_ns(url_elem, "changefreq"))

        entries.append(
            SitemapEntry(
                url=loc,
                lastmod=lastmod,
                priority=priority,
                changefreq=changefreq,
            )
        )

    return entries


def parse_sitemap_index(content: str | bytes) -> list[str]:
    """
    Parse a sitemap index file and extract sitemap URLs.

    Args:
        content: Sitemap index XML content.

    Returns:
        List of sitemap URLs.
    """
    if isinstance(content, bytes):
        content = _decompress_if_gzip(content)
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            content = content.decode("latin-1")

    sitemap_urls: list[str] = []

    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return sitemap_urls

    # Find all <sitemap> elements
    sitemap_elements = _findall_with_ns(root, "sitemap")

    for sitemap_elem in sitemap_elements:
        loc_elem = _find_with_ns(sitemap_elem, "loc")
        loc = _get_text(loc_elem)

        if loc:
            sitemap_urls.append(loc)

    return sitemap_urls


def _is_sitemap_index(content: str | bytes) -> bool:
    """
    Detect if content is a sitemap index vs regular sitemap.

    Args:
        content: XML content to check.

    Returns:
        True if content is a sitemap index.
    """
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            content = content.decode("latin-1")

    return "sitemapindex" in content.lower()


@dataclass
class SitemapParser:
    """
    Sitemap parser with support for index files and compression.

    Parses sitemap.xml files and sitemap index files,
    following index references to child sitemaps.

    Usage:
        parser = SitemapParser()
        entries = await parser.parse("https://example.com/sitemap.xml")
    """

    settings: SitemapSettings = field(default_factory=SitemapSettings)

    async def parse(self, url: str) -> list[SitemapEntry]:
        """
        Parse a sitemap URL and return all URL entries.

        Handles both regular sitemaps and sitemap index files.
        Automatically decompresses gzip sitemaps.

        Args:
            url: Sitemap URL to parse.

        Returns:
            List of SitemapEntry objects (deduplicated).
        """
        if not self.settings.use_sitemaps:
            return []

        entries: list[SitemapEntry] = []
        seen_urls: set[str] = set()

        async def process_sitemap(sitemap_url: str, depth: int = 0) -> None:
            """Recursively process sitemap URLs."""
            if len(entries) >= self.settings.max_urls:
                return

            if depth > 2:  # Prevent infinite recursion
                return

            try:
                content = await fetch_sitemap(sitemap_url, self.settings.timeout_seconds)

                # Decompress if needed
                content = _decompress_if_gzip(content)

                # Check if this is a sitemap index
                if _is_sitemap_index(content):
                    child_urls = parse_sitemap_index(content)
                    for child_url in child_urls:
                        if len(entries) >= self.settings.max_urls:
                            break
                        await process_sitemap(child_url, depth + 1)
                else:
                    # Regular sitemap
                    sitemap_entries = parse_sitemap_xml(content)
                    for entry in sitemap_entries:
                        if len(entries) >= self.settings.max_urls:
                            break
                        if entry.url not in seen_urls:
                            seen_urls.add(entry.url)
                            entries.append(entry)

            except Exception:
                # Silently skip failed sitemaps
                pass

        await process_sitemap(url)
        return entries

    async def parse_many(self, urls: list[str]) -> list[SitemapEntry]:
        """
        Parse multiple sitemap URLs and return all entries.

        Args:
            urls: List of sitemap URLs to parse.

        Returns:
            Combined list of SitemapEntry objects (deduplicated).
        """
        all_entries: list[SitemapEntry] = []
        seen_urls: set[str] = set()

        for url in urls:
            if len(all_entries) >= self.settings.max_urls:
                break

            entries = await self.parse(url)
            for entry in entries:
                if entry.url not in seen_urls:
                    seen_urls.add(entry.url)
                    all_entries.append(entry)
                    if len(all_entries) >= self.settings.max_urls:
                        break

        return all_entries
