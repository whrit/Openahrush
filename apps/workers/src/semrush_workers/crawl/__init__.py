"""
Crawl engine components for Openahrush.

Provides:
- Frontier management for URL queue
- HTTP fetching with politeness
- HTML extraction
- Hybrid JS rendering with heuristics
- Render orchestration
- Crawl orchestrator for full crawl lifecycle
"""

from __future__ import annotations

from semrush_workers.crawl.events import (
    CrawlEvent,
    EventType,
    NoOpEventEmitter,
    RedisEventEmitter,
)
from semrush_workers.crawl.fetcher import (
    Fetcher,
    FetchError,
    FetcherSettings,
    FetchResult,
)
from semrush_workers.crawl.frontier import (
    Frontier,
    FrontierSettings,
)
from semrush_workers.crawl.models import (
    AnalysisResult,
    CrawlRun,
    CrawlSettings,
    CrawlStatus,
    Link,
    PageData,
    RenderedResult,
)
from semrush_workers.crawl.orchestrator import CrawlOrchestrator

__all__ = [
    # Models
    "AnalysisResult",
    "CrawlRun",
    "CrawlSettings",
    "CrawlStatus",
    "Link",
    "PageData",
    "RenderedResult",
    # Orchestrator
    "CrawlOrchestrator",
    # Frontier
    "Frontier",
    "FrontierSettings",
    # Fetcher
    "FetchError",
    "FetchResult",
    "Fetcher",
    "FetcherSettings",
    # Events
    "CrawlEvent",
    "EventType",
    "NoOpEventEmitter",
    "RedisEventEmitter",
]
