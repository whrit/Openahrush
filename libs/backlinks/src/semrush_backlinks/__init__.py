"""
Openahrush Backlinks Library.

Provides backlink analysis capabilities including:
- Common Crawl data ingestion
- Backlink data models
- Link quality analysis

Note: This is a placeholder package. Full implementation pending.
"""

__version__ = "0.1.0"

from semrush_backlinks.models import (
    Backlink,
    BacklinkSource,
    LinkType,
)

__all__ = [
    "Backlink",
    "BacklinkSource",
    "LinkType",
    "__version__",
]
