"""
Openahrush SEO Utilities Library.

Provides SEO-specific utilities including:
- URL normalization and canonicalization
- Domain extraction and validation
- Query parameter handling
"""

__version__ = "0.1.0"

from semrush_seo.url import (
    URLInfo,
    canonicalize_url,
    extract_domain,
    normalize_url,
    parse_url,
)

__all__ = [
    "URLInfo",
    "__version__",
    "canonicalize_url",
    "extract_domain",
    "normalize_url",
    "parse_url",
]
