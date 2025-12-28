"""
URL normalization and parsing utilities for SEO analysis.

Provides consistent URL handling for:
- Crawling (normalize URLs for deduplication)
- Backlink analysis (extract domains, compare URLs)
- Reporting (display canonical URLs)
"""

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import tldextract


@dataclass(frozen=True, slots=True)
class URLInfo:
    """
    Parsed and normalized URL information.

    Attributes:
        original: Original URL as provided.
        normalized: Normalized URL for comparison.
        scheme: URL scheme (http/https).
        subdomain: Subdomain portion (e.g., "www", "blog").
        domain: Registered domain (e.g., "example").
        suffix: Public suffix (e.g., "com", "co.uk").
        registered_domain: Full registered domain (domain + suffix).
        path: Normalized URL path.
        query: Query string (sorted, normalized).
        fragment: URL fragment (usually stripped for SEO).
    """

    original: str
    normalized: str
    scheme: str
    subdomain: str
    domain: str
    suffix: str
    registered_domain: str
    path: str
    query: str
    fragment: str

    @property
    def full_domain(self) -> str:
        """Get the full domain including subdomain."""
        if self.subdomain:
            return f"{self.subdomain}.{self.registered_domain}"
        return self.registered_domain

    @property
    def is_https(self) -> bool:
        """Check if URL uses HTTPS."""
        return self.scheme == "https"

    @property
    def is_www(self) -> bool:
        """Check if URL uses www subdomain."""
        return self.subdomain == "www"

    @property
    def path_depth(self) -> int:
        """Get the depth of the URL path."""
        if not self.path or self.path == "/":
            return 0
        return len([p for p in self.path.split("/") if p])


# Common tracking parameters to remove during normalization
TRACKING_PARAMS: set[str] = {
    # Google Analytics / Google Ads
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "gclsrc",
    # Facebook
    "fbclid",
    "fb_action_ids",
    "fb_action_types",
    "fb_source",
    "fb_ref",
    # Microsoft / Bing
    "msclkid",
    # Other common trackers
    "mc_cid",
    "mc_eid",
    "ref",
    "_ga",
    "_gl",
    "yclid",
    "wickedid",
    "twclid",
    # Email tracking
    "mkt_tok",
    "trk",
}

# Parameters that should always be kept
KEEP_PARAMS: set[str] = {
    "page",
    "p",
    "q",
    "query",
    "search",
    "id",
    "product",
    "category",
    "sort",
    "order",
    "filter",
    "lang",
    "locale",
}


def normalize_url(
    url: str,
    *,
    remove_trailing_slash: bool = True,
    lowercase_path: bool = True,
    remove_fragments: bool = True,
    remove_tracking_params: bool = True,
    sort_query_params: bool = True,
    force_https: bool = False,
    remove_www: bool = False,
    add_www: bool = False,
) -> str:
    """
    Normalize a URL for consistent comparison and storage.

    This is the primary normalization function for deduplicating URLs
    during crawling and backlink analysis.

    Args:
        url: URL string to normalize.
        remove_trailing_slash: Remove trailing slash from path (default True).
        lowercase_path: Convert path to lowercase (default True).
        remove_fragments: Remove URL fragments/anchors (default True).
        remove_tracking_params: Remove UTM and tracking params (default True).
        sort_query_params: Sort query parameters alphabetically (default True).
        force_https: Upgrade http to https (default False).
        remove_www: Remove www subdomain (default False).
        add_www: Add www subdomain if missing (default False).

    Returns:
        Normalized URL string.

    Raises:
        ValueError: If URL is invalid or cannot be parsed.

    Examples:
        >>> normalize_url("HTTPS://WWW.Example.COM/Path/?utm_source=google&b=2&a=1")
        'https://www.example.com/path?a=1&b=2'

        >>> normalize_url("http://example.com/page/", remove_trailing_slash=True)
        'http://example.com/page'
    """
    if not url or not url.strip():
        raise ValueError("URL cannot be empty")

    url = url.strip()
    url_lower = url.lower()

    # Add scheme if missing (case-insensitive check)
    if not url_lower.startswith(("http://", "https://", "//")):
        url = "https://" + url
    # Handle protocol-relative URLs
    elif url_lower.startswith("//"):
        url = "https:" + url

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValueError(f"Invalid URL: {url}") from e

    if not parsed.netloc:
        raise ValueError(f"URL missing domain: {url}")

    # Normalize scheme
    scheme = parsed.scheme.lower()
    if force_https and scheme == "http":
        scheme = "https"

    # Normalize netloc (domain)
    netloc = parsed.netloc.lower()

    # Handle www normalization
    if remove_www and netloc.startswith("www."):
        netloc = netloc[4:]
    elif add_www and not netloc.startswith("www."):
        netloc = "www." + netloc

    # Remove default ports
    netloc = re.sub(r":80$", "", netloc)
    netloc = re.sub(r":443$", "", netloc)

    # Normalize path
    path = parsed.path
    if lowercase_path:
        path = path.lower()

    # Collapse multiple slashes
    path = re.sub(r"/+", "/", path)

    # Handle trailing slash
    if remove_trailing_slash and path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")

    # Ensure path starts with /
    if not path:
        path = "/"

    # Normalize query parameters
    query = ""
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)

        # Filter out tracking parameters
        if remove_tracking_params:
            params = {
                k: v
                for k, v in params.items()
                if k.lower() not in TRACKING_PARAMS or k.lower() in KEEP_PARAMS
            }

        # Sort and rebuild query string
        if params:
            if sort_query_params:
                sorted_params = sorted(params.items())
            else:
                sorted_params = list(params.items())

            # Flatten lists to single values where possible
            flat_params = []
            for key, values in sorted_params:
                for value in values:
                    flat_params.append((key, value))

            query = urlencode(flat_params)

    # Handle fragment
    fragment = "" if remove_fragments else parsed.fragment

    # Reconstruct URL
    normalized = urlunparse((scheme, netloc, path, "", query, fragment))

    return normalized


def canonicalize_url(
    url: str,
    *,
    prefer_https: bool = True,
    prefer_www: Literal["www", "non-www", "keep"] = "keep",
) -> str:
    """
    Create a canonical URL for SEO purposes.

    Similar to normalize_url but with more aggressive canonicalization
    suitable for determining the "official" version of a URL.

    Args:
        url: URL to canonicalize.
        prefer_https: Use HTTPS if available.
        prefer_www: How to handle www subdomain.

    Returns:
        Canonical URL string.
    """
    remove_www = prefer_www == "non-www"
    add_www = prefer_www == "www"

    return normalize_url(
        url,
        remove_trailing_slash=True,
        lowercase_path=True,
        remove_fragments=True,
        remove_tracking_params=True,
        sort_query_params=True,
        force_https=prefer_https,
        remove_www=remove_www,
        add_www=add_www,
    )


def extract_domain(url: str) -> str:
    """
    Extract the registered domain from a URL.

    Uses the Public Suffix List to correctly handle multi-part TLDs
    like .co.uk, .com.au, etc.

    Args:
        url: URL to extract domain from.

    Returns:
        Registered domain (e.g., "example.com", "example.co.uk").

    Examples:
        >>> extract_domain("https://blog.example.co.uk/page")
        'example.co.uk'

        >>> extract_domain("https://sub.domain.example.com")
        'example.com'
    """
    extracted = tldextract.extract(url)
    return extracted.registered_domain


def parse_url(url: str) -> URLInfo:
    """
    Parse a URL into its component parts with normalization.

    Provides detailed URL information useful for SEO analysis,
    including proper handling of subdomains and public suffixes.

    Args:
        url: URL to parse.

    Returns:
        URLInfo with all URL components.

    Examples:
        >>> info = parse_url("https://blog.example.co.uk/path?q=1")
        >>> info.subdomain
        'blog'
        >>> info.registered_domain
        'example.co.uk'
    """
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    extracted = tldextract.extract(url)

    return URLInfo(
        original=url,
        normalized=normalized,
        scheme=parsed.scheme,
        subdomain=extracted.subdomain,
        domain=extracted.domain,
        suffix=extracted.suffix,
        registered_domain=extracted.registered_domain,
        path=parsed.path,
        query=parsed.query,
        fragment=parsed.fragment,
    )


def urls_are_equivalent(url1: str, url2: str) -> bool:
    """
    Check if two URLs point to the same resource.

    Uses normalization to compare URLs, ignoring differences in:
    - Case
    - Trailing slashes
    - Query parameter order
    - Tracking parameters
    - Fragments

    Args:
        url1: First URL to compare.
        url2: Second URL to compare.

    Returns:
        True if URLs are equivalent, False otherwise.

    Examples:
        >>> urls_are_equivalent(
        ...     "https://Example.com/PATH/?utm_source=google",
        ...     "https://example.com/path"
        ... )
        True
    """
    try:
        return normalize_url(url1) == normalize_url(url2)
    except ValueError:
        return False


def is_internal_url(url: str, base_domain: str) -> bool:
    """
    Check if a URL belongs to the same domain.

    Useful for crawling to distinguish internal vs external links.

    Args:
        url: URL to check.
        base_domain: Domain to compare against (e.g., "example.com").

    Returns:
        True if URL is on the same registered domain.

    Examples:
        >>> is_internal_url("https://blog.example.com/page", "example.com")
        True
        >>> is_internal_url("https://other.com/page", "example.com")
        False
    """
    url_domain = extract_domain(url)
    base = extract_domain(base_domain) if "." in base_domain else base_domain

    return url_domain.lower() == base.lower()


def get_url_path_parts(url: str) -> list[str]:
    """
    Get the path segments of a URL.

    Useful for analyzing URL structure and depth.

    Args:
        url: URL to extract path from.

    Returns:
        List of path segments (excluding empty segments).

    Examples:
        >>> get_url_path_parts("https://example.com/blog/2024/post-title")
        ['blog', '2024', 'post-title']
    """
    parsed = urlparse(normalize_url(url))
    return [p for p in parsed.path.split("/") if p]
