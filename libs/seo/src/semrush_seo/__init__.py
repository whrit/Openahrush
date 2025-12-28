"""
Openahrush SEO Utilities Library.

Provides SEO-specific utilities including:
- URL normalization and canonicalization
- Domain extraction and validation
- Query parameter handling
- robots.txt parsing and URL allowance checking
- Sitemap parsing (XML and index files)
- HTML content extraction for SEO analysis
"""

__version__ = "0.1.0"

from semrush_seo.extraction import (
    Link,
    PageData,
    compute_html_hash,
    extract_links,
    extract_meta_tags,
    extract_page_data,
)
from semrush_seo.robots import (
    RobotsData,
    RobotsParser,
    RobotsRule,
    RobotsSettings,
    fetch_robots_txt,
    is_allowed,
    parse_robots_txt,
)
from semrush_seo.sitemap import (
    SitemapEntry,
    SitemapParser,
    SitemapSettings,
    fetch_sitemap,
    parse_sitemap_index,
    parse_sitemap_xml,
)
from semrush_seo.url import (
    URLInfo,
    canonicalize_url,
    extract_domain,
    normalize_url,
    parse_url,
)

__all__ = [
    # Version
    "__version__",
    # URL utilities
    "URLInfo",
    "canonicalize_url",
    "extract_domain",
    "normalize_url",
    "parse_url",
    # Robots.txt
    "RobotsData",
    "RobotsParser",
    "RobotsRule",
    "RobotsSettings",
    "fetch_robots_txt",
    "is_allowed",
    "parse_robots_txt",
    # Sitemap
    "SitemapEntry",
    "SitemapParser",
    "SitemapSettings",
    "fetch_sitemap",
    "parse_sitemap_index",
    "parse_sitemap_xml",
    # Extraction
    "Link",
    "PageData",
    "compute_html_hash",
    "extract_links",
    "extract_meta_tags",
    "extract_page_data",
]
