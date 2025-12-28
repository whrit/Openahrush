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
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from lxml import html
from lxml.html import HtmlElement


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


def extract_meta_tags(html_content: str) -> dict[str, str]:
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


def extract_links(
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


def extract_page_data(
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

    internal_links, external_links = extract_links(html_content, url, base_domain)

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
