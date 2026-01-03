"""
HTML content extraction for SEO analysis.

Provides extraction of SEO-relevant data from HTML including:
- Title and meta description
- Canonical URL and meta robots
- H1 tags (count and first text)
- Word count and text length
- Internal and external links
- Script sources
- HTML content hash

Performance optimization:
- Uses selectolax (5-10x faster than lxml) as primary parser
- Falls back to lxml for edge cases requiring full CSS selector support
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urljoin, urlparse

from lxml import html
from lxml.html import HtmlElement
from selectolax.parser import HTMLParser as SelectolaxParser

logger = logging.getLogger(__name__)


class ParserBackend(Enum):
    """Available HTML parser backends."""

    SELECTOLAX = "selectolax"
    LXML = "lxml"


@dataclass
class Link:
    """
    Represents a link extracted from a page.

    Attributes:
        href: Target URL of the link.
        text: Anchor text of the link.
        rel: Rel attribute value (nofollow, sponsored, ugc, etc.).
        is_internal: Whether the link is internal to the site.
    """

    href: str
    text: str | None = None
    rel: str | None = None
    is_internal: bool = True

    @property
    def is_nofollow(self) -> bool:
        """Check if link has nofollow attribute."""
        if not self.rel:
            return False
        return "nofollow" in self.rel.lower()

    @property
    def is_sponsored(self) -> bool:
        """Check if link has sponsored attribute."""
        if not self.rel:
            return False
        return "sponsored" in self.rel.lower()

    @property
    def is_ugc(self) -> bool:
        """Check if link has ugc (user-generated content) attribute."""
        if not self.rel:
            return False
        return "ugc" in self.rel.lower()


@dataclass
class PageData:
    """
    Extracted SEO data from a page.

    Attributes:
        url: The page URL.
        title: Title tag content.
        meta_description: Meta description content.
        canonical: Canonical URL if specified.
        meta_robots: Meta robots directive.
        h1_count: Number of H1 tags.
        h1_first: Content of first H1 tag.
        word_count: Approximate word count.
        text_length: Total text character count.
        internal_links: List of internal links.
        external_links: List of external links.
        scripts: List of script source URLs.
        html_hash: Hash of the HTML content.
    """

    url: str
    title: str | None = None
    meta_description: str | None = None
    canonical: str | None = None
    meta_robots: str | None = None
    h1_count: int = 0
    h1_first: str | None = None
    word_count: int = 0
    text_length: int = 0
    internal_links: list[Link] = field(default_factory=list)
    external_links: list[Link] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    html_hash: str = ""


def compute_html_hash(html_content: str) -> str:
    """
    Compute a hash of HTML content for change detection.

    Args:
        html_content: HTML content as string.

    Returns:
        SHA256 hash of the content (first 16 characters).
    """
    if not html_content:
        return ""
    content_bytes = html_content.encode("utf-8")
    return hashlib.sha256(content_bytes).hexdigest()[:16]


def _get_text_content(element: HtmlElement) -> str:
    """
    Get text content from an element, stripping whitespace.

    Args:
        element: lxml HtmlElement.

    Returns:
        Stripped text content.
    """
    text = element.text_content()
    if text:
        return " ".join(text.split())
    return ""


def _is_internal_url(url: str, base_domain: str) -> bool:
    """
    Check if a URL is internal to the base domain.

    Args:
        url: URL to check.
        base_domain: Base domain for comparison.

    Returns:
        True if URL is internal.
    """
    try:
        parsed = urlparse(url)
        # Relative URLs are internal
        if not parsed.netloc:
            return True
        # Compare domains (case-insensitive)
        url_domain = parsed.netloc.lower()
        base = base_domain.lower()
        # Handle www variations
        url_domain = url_domain.removeprefix("www.")
        base = base.removeprefix("www.")
        return url_domain == base or url_domain.endswith("." + base)
    except Exception:
        return True  # Default to internal on parsing error


def _is_crawlable_url(url: str) -> bool:
    """
    Check if a URL scheme is crawlable.

    Args:
        url: URL to check.

    Returns:
        True if URL can be crawled.
    """
    if not url:
        return False
    url_lower = url.strip().lower()
    # Skip non-HTTP schemes
    skip_schemes = (
        "javascript:",
        "mailto:",
        "tel:",
        "data:",
        "#",
        "ftp:",
        "file:",
    )
    return not any(url_lower.startswith(scheme) for scheme in skip_schemes)


class FastHTMLParser:
    """
    High-performance HTML parser using selectolax.

    Selectolax is 5-10x faster than lxml for HTML parsing, making it
    ideal for high-throughput crawling workloads. This parser provides
    the same extraction capabilities as the lxml-based functions.

    Usage:
        parser = FastHTMLParser()
        page_data = parser.extract_page_data(html, url, domain)
    """

    def __init__(self, strip_whitespace: bool = True) -> None:
        """
        Initialize the fast HTML parser.

        Args:
            strip_whitespace: Whether to strip whitespace from extracted text.
        """
        self.strip_whitespace = strip_whitespace

    def _normalize_text(self, text: str | None) -> str:
        """Normalize text by collapsing whitespace."""
        if not text:
            return ""
        if self.strip_whitespace:
            return " ".join(text.split())
        return text

    def extract_title(self, tree: SelectolaxParser) -> str | None:
        """Extract title from parsed HTML tree."""
        title_node = tree.css_first("title")
        if title_node:
            text = self._normalize_text(title_node.text())
            return text if text else None
        return None

    def extract_meta_description(self, tree: SelectolaxParser) -> str | None:
        """Extract meta description from parsed HTML tree."""
        for meta in tree.css("meta"):
            name = meta.attributes.get("name", "")
            if name and name.lower() == "description":
                content = meta.attributes.get("content")
                if content:
                    return content.strip()
        return None

    def extract_canonical(self, tree: SelectolaxParser, base_url: str) -> str | None:
        """Extract canonical URL from parsed HTML tree."""
        for link in tree.css("link"):
            rel = link.attributes.get("rel", "")
            if rel and rel.lower() == "canonical":
                href = link.attributes.get("href")
                if href:
                    return urljoin(base_url, href.strip())
        return None

    def extract_meta_robots(self, tree: SelectolaxParser) -> str | None:
        """Extract meta robots directive from parsed HTML tree."""
        for meta in tree.css("meta"):
            name = meta.attributes.get("name", "")
            if name and name.lower() == "robots":
                content = meta.attributes.get("content")
                if content:
                    return content.strip()
        return None

    def extract_h1s(self, tree: SelectolaxParser) -> tuple[int, str | None]:
        """
        Extract H1 information from parsed HTML tree.

        Returns:
            Tuple of (h1_count, first_h1_text).
        """
        h1_nodes = tree.css("h1")
        h1_count = len(h1_nodes)
        h1_first = None
        if h1_nodes:
            text = self._normalize_text(h1_nodes[0].text())
            h1_first = text if text else None
        return h1_count, h1_first

    def extract_text_metrics(self, tree: SelectolaxParser) -> tuple[int, int]:
        """
        Extract text metrics (word count, text length) from parsed HTML tree.

        Returns:
            Tuple of (word_count, text_length).
        """
        # Remove script and style elements from a copy
        for tag in tree.css("script, style"):
            tag.decompose()

        # Get body text or full document text
        body = tree.css_first("body")
        if body:
            text = self._normalize_text(body.text())
        else:
            text = self._normalize_text(tree.text())

        text_length = len(text)
        word_count = len(text.split()) if text else 0

        return word_count, text_length

    def extract_links_from_tree(
        self,
        tree: SelectolaxParser,
        base_url: str,
        base_domain: str,
    ) -> tuple[list[Link], list[Link]]:
        """
        Extract internal and external links from parsed HTML tree.

        Returns:
            Tuple of (internal_links, external_links).
        """
        internal_links: list[Link] = []
        external_links: list[Link] = []

        for anchor in tree.css("a"):
            href = anchor.attributes.get("href", "")
            if not href:
                continue
            href = href.strip()

            if not _is_crawlable_url(href):
                continue

            # Resolve relative URLs
            try:
                absolute_url = urljoin(base_url, href)
            except Exception:
                continue

            text = self._normalize_text(anchor.text()) or None
            rel = anchor.attributes.get("rel")

            is_internal = _is_internal_url(absolute_url, base_domain)

            link = Link(
                href=absolute_url,
                text=text,
                rel=rel,
                is_internal=is_internal,
            )

            if is_internal:
                internal_links.append(link)
            else:
                external_links.append(link)

        return internal_links, external_links

    def extract_scripts(self, tree: SelectolaxParser, base_url: str) -> list[str]:
        """Extract external script sources from parsed HTML tree."""
        scripts: list[str] = []
        for script in tree.css("script"):
            src = script.attributes.get("src")
            if src:
                scripts.append(urljoin(base_url, src.strip()))
        return scripts

    def extract_page_data(
        self,
        html_content: str,
        url: str,
        base_domain: str,
    ) -> PageData:
        """
        Extract all SEO-relevant data from HTML content.

        Args:
            html_content: HTML content as string.
            url: The page URL.
            base_domain: Domain for internal/external link classification.

        Returns:
            PageData with all extracted information.
        """
        html_hash = compute_html_hash(html_content)

        if not html_content:
            return PageData(url=url, html_hash=html_hash)

        try:
            tree = SelectolaxParser(html_content)
        except Exception:
            return PageData(url=url, html_hash=html_hash)

        # Extract all data
        title = self.extract_title(tree)
        meta_description = self.extract_meta_description(tree)
        canonical = self.extract_canonical(tree, url)
        meta_robots = self.extract_meta_robots(tree)
        h1_count, h1_first = self.extract_h1s(tree)

        # Fresh parse for links and scripts since text metrics modifies tree
        try:
            links_tree = SelectolaxParser(html_content)
            internal_links, external_links = self.extract_links_from_tree(
                links_tree, url, base_domain
            )
            scripts = self.extract_scripts(links_tree, url)
        except Exception:
            internal_links, external_links = [], []
            scripts = []

        # Extract text metrics (modifies tree by removing script/style)
        try:
            metrics_tree = SelectolaxParser(html_content)
            word_count, text_length = self.extract_text_metrics(metrics_tree)
        except Exception:
            word_count, text_length = 0, 0

        return PageData(
            url=url,
            title=title,
            meta_description=meta_description,
            canonical=canonical,
            meta_robots=meta_robots,
            h1_count=h1_count,
            h1_first=h1_first,
            word_count=word_count,
            text_length=text_length,
            internal_links=internal_links,
            external_links=external_links,
            scripts=scripts,
            html_hash=html_hash,
        )

    def extract_links(
        self,
        html_content: str,
        base_url: str,
        base_domain: str,
    ) -> tuple[list[Link], list[Link]]:
        """
        Extract internal and external links from HTML.

        Args:
            html_content: HTML content as string.
            base_url: Base URL for resolving relative links.
            base_domain: Domain for internal/external classification.

        Returns:
            Tuple of (internal_links, external_links).
        """
        if not html_content:
            return [], []

        try:
            tree = SelectolaxParser(html_content)
            return self.extract_links_from_tree(tree, base_url, base_domain)
        except Exception:
            return [], []

    def extract_meta_tags(self, html_content: str) -> dict[str, str]:
        """
        Extract all meta tags from HTML.

        Args:
            html_content: HTML content as string.

        Returns:
            Dictionary of meta tag name/property to content.
        """
        if not html_content:
            return {}

        try:
            tree = SelectolaxParser(html_content)
        except Exception:
            return {}

        meta_tags: dict[str, str] = {}

        for meta in tree.css("meta"):
            name = meta.attributes.get("name") or meta.attributes.get("property")
            content = meta.attributes.get("content")
            if name and content:
                meta_tags[name.lower()] = content

        return meta_tags


# Default parser instance for high-performance parsing
_fast_parser = FastHTMLParser()


# ---------------------------------------------------------------------------
# lxml-based functions (kept for backward compatibility)
# ---------------------------------------------------------------------------


def _extract_meta_tags_lxml(html_content: str) -> dict[str, str]:
    """
    Extract all meta tags from HTML using lxml.

    Args:
        html_content: HTML content as string.

    Returns:
        Dictionary of meta tag name/property to content.
    """
    if not html_content:
        return {}

    try:
        doc = html.fromstring(html_content)
    except Exception:
        return {}

    meta_tags: dict[str, str] = {}

    for meta in doc.cssselect("meta"):
        name = meta.get("name") or meta.get("property")
        content = meta.get("content")
        if name and content:
            meta_tags[name.lower()] = content

    return meta_tags


def extract_meta_tags(
    html_content: str,
    backend: ParserBackend = ParserBackend.SELECTOLAX,
) -> dict[str, str]:
    """
    Extract all meta tags from HTML.

    Args:
        html_content: HTML content as string.
        backend: Parser backend to use (default: selectolax for performance).

    Returns:
        Dictionary of meta tag name/property to content.
    """
    if backend == ParserBackend.LXML:
        return _extract_meta_tags_lxml(html_content)
    return _fast_parser.extract_meta_tags(html_content)


def _extract_links_lxml(
    html_content: str,
    base_url: str,
    base_domain: str,
) -> tuple[list[Link], list[Link]]:
    """
    Extract internal and external links from HTML using lxml.

    Args:
        html_content: HTML content as string.
        base_url: Base URL for resolving relative links.
        base_domain: Domain for internal/external classification.

    Returns:
        Tuple of (internal_links, external_links).
    """
    if not html_content:
        return [], []

    try:
        doc = html.fromstring(html_content)
    except Exception:
        return [], []

    internal_links: list[Link] = []
    external_links: list[Link] = []

    for anchor in doc.cssselect("a[href]"):
        href = anchor.get("href", "").strip()

        if not _is_crawlable_url(href):
            continue

        # Resolve relative URLs
        try:
            absolute_url = urljoin(base_url, href)
        except Exception:
            continue

        text = _get_text_content(anchor) or None
        rel = anchor.get("rel")
        if rel:
            rel = " ".join(rel) if isinstance(rel, list) else rel

        is_internal = _is_internal_url(absolute_url, base_domain)

        link = Link(
            href=absolute_url,
            text=text,
            rel=rel,
            is_internal=is_internal,
        )

        if is_internal:
            internal_links.append(link)
        else:
            external_links.append(link)

    return internal_links, external_links


def extract_links(
    html_content: str,
    base_url: str,
    base_domain: str,
    backend: ParserBackend = ParserBackend.SELECTOLAX,
) -> tuple[list[Link], list[Link]]:
    """
    Extract internal and external links from HTML.

    Args:
        html_content: HTML content as string.
        base_url: Base URL for resolving relative links.
        base_domain: Domain for internal/external classification.
        backend: Parser backend to use (default: selectolax for performance).

    Returns:
        Tuple of (internal_links, external_links).
    """
    if backend == ParserBackend.LXML:
        return _extract_links_lxml(html_content, base_url, base_domain)
    return _fast_parser.extract_links(html_content, base_url, base_domain)


def _extract_page_data_lxml(
    html_content: str,
    url: str,
    base_domain: str,
) -> PageData:
    """
    Extract all SEO-relevant data from HTML content using lxml.

    Args:
        html_content: HTML content as string.
        url: The page URL.
        base_domain: Domain for internal/external link classification.

    Returns:
        PageData with all extracted information.
    """
    if not html_content:
        return PageData(
            url=url,
            html_hash=compute_html_hash(html_content),
        )

    try:
        doc = html.fromstring(html_content)
    except Exception:
        return PageData(
            url=url,
            html_hash=compute_html_hash(html_content),
        )

    # Extract title
    title = None
    title_elems = doc.cssselect("title")
    if title_elems:
        title = _get_text_content(title_elems[0])
        if not title:
            title = None

    # Extract meta description (take first)
    meta_description = None
    for meta in doc.cssselect("meta"):
        name = (meta.get("name") or "").lower()
        if name == "description":
            content = meta.get("content")
            if content:
                meta_description = content.strip()
                break

    # Extract canonical
    canonical = None
    for link in doc.cssselect("link[rel='canonical']"):
        href = link.get("href")
        if href:
            canonical = urljoin(url, href.strip())
            break

    # Extract meta robots
    meta_robots = None
    for meta in doc.cssselect("meta"):
        name = (meta.get("name") or "").lower()
        if name == "robots":
            content = meta.get("content")
            if content:
                meta_robots = content.strip()
                break

    # Extract H1s
    h1_elements = doc.cssselect("h1")
    h1_count = len(h1_elements)
    h1_first = None
    if h1_elements:
        h1_first = _get_text_content(h1_elements[0])
        if not h1_first:
            h1_first = None

    # Extract text for word count (exclude script/style)
    # Remove script and style elements
    for element in doc.cssselect("script, style"):
        element.drop_tree()

    # Get text content from body
    body_elements = doc.cssselect("body")
    if body_elements:
        text = _get_text_content(body_elements[0])
    else:
        text = _get_text_content(doc)

    text_length = len(text)
    # Word count: split on whitespace
    words = text.split()
    word_count = len(words)

    # Extract links
    # Re-parse since we modified the doc
    try:
        doc_links = html.fromstring(html_content)
    except Exception:
        doc_links = doc

    internal_links, external_links = _extract_links_lxml(html_content, url, base_domain)

    # Extract script sources
    scripts: list[str] = []
    try:
        for script in doc_links.cssselect("script[src]"):
            src = script.get("src")
            if src:
                scripts.append(urljoin(url, src.strip()))
    except Exception:
        pass

    return PageData(
        url=url,
        title=title,
        meta_description=meta_description,
        canonical=canonical,
        meta_robots=meta_robots,
        h1_count=h1_count,
        h1_first=h1_first,
        word_count=word_count,
        text_length=text_length,
        internal_links=internal_links,
        external_links=external_links,
        scripts=scripts,
        html_hash=compute_html_hash(html_content),
    )


def extract_page_data(
    html_content: str,
    url: str,
    base_domain: str,
    backend: ParserBackend = ParserBackend.SELECTOLAX,
) -> PageData:
    """
    Extract all SEO-relevant data from HTML content.

    Args:
        html_content: HTML content as string.
        url: The page URL.
        base_domain: Domain for internal/external link classification.
        backend: Parser backend to use (default: selectolax for performance).

    Returns:
        PageData with all extracted information.
    """
    if backend == ParserBackend.LXML:
        return _extract_page_data_lxml(html_content, url, base_domain)
    return _fast_parser.extract_page_data(html_content, url, base_domain)


def get_parser(backend: ParserBackend = ParserBackend.SELECTOLAX) -> FastHTMLParser:
    """
    Get a parser instance.

    For high-throughput scenarios, reusing a parser instance is more efficient.

    Args:
        backend: Parser backend to use.

    Returns:
        FastHTMLParser instance.
    """
    if backend == ParserBackend.SELECTOLAX:
        return _fast_parser
    # For lxml, we still return the fast parser but callers can use
    # the module-level functions with backend=ParserBackend.LXML
    return _fast_parser
