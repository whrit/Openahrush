"""
Openahrush Common Crawl Ingest.

Pipeline for ingesting backlink data from Common Crawl:
- WARC file processing
- Link extraction and normalization
- Incremental ingestion with checkpointing
- ClickHouse storage for analytics

Features:
- Resume-capable ingestion
- Parallel processing
- Domain filtering
- Quality scoring

Storage Adapters:
- PostgresStorage: MVP storage using SQLAlchemy async
- ClickHouseStorage: Placeholder for scale implementation

See COMMONCRAWL_INGESTION.md for detailed design.
"""

__version__ = "0.1.0"

from enum import StrEnum

from semrush_commoncrawl.aggregates import (
    AggregateBuilder,
    AggregateResult,
    AnchorsAggregator,
    RefDomainsAggregator,
)
from semrush_commoncrawl.batch_inserter import BatchInserter
from semrush_commoncrawl.checkpoint import IngestionCheckpoint

# Pipeline components
from semrush_commoncrawl.downloader import (
    DownloadError,
    WatDownloader,
    download_wat_file,
    fetch_wat_paths,
)
from semrush_commoncrawl.filter import DomainFilter, FilterStats
from semrush_commoncrawl.optimized_orchestrator import (
    OptimizedIngestionOrchestrator,
    OptimizedIngestionResult,
    OptimizedIngestionSettings,
    OptimizedIngestSpec,
)
from semrush_commoncrawl.orchestrator import (
    IngestionOrchestrator,
    IngestionProgress,
    IngestionResult,
    IngestionSettings,
    IngestSpec,
)
from semrush_commoncrawl.parallel import ProcessingResult, process_wat_files_parallel
from semrush_commoncrawl.parser import Edge as ParsedEdge  # Renamed to avoid conflict
from semrush_commoncrawl.parser import parse_rel_flags, parse_wat_records
from semrush_commoncrawl.storage import (
    AnchorCount,
    Backlink,
    ClickHouseStorage,
    Edge,
    EdgeStorage,
    PostgresStorage,
    RefDomain,
    get_storage,
)
from semrush_commoncrawl.storage.clickhouse_async import (
    ClickHouseAsyncConfig,
    ClickHouseAsyncStorage,
)
from semrush_commoncrawl.streaming import stream_parse_wat, stream_parse_wat_batched


class IngestStatus(StrEnum):
    """Status of an ingestion job."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CrawlIndex(StrEnum):
    """Available Common Crawl indexes."""

    # These are example indexes - actual indexes are dated
    LATEST = "CC-MAIN-2024-10"
    # Add more as needed


__all__ = [
    # Enums
    "IngestStatus",
    "CrawlIndex",
    # Aggregates
    "AggregateBuilder",
    "AggregateResult",
    "AnchorsAggregator",
    "RefDomainsAggregator",
    # Storage
    "AnchorCount",
    "Backlink",
    "ClickHouseStorage",
    "Edge",
    "EdgeStorage",
    "PostgresStorage",
    "RefDomain",
    "get_storage",
    # Downloader
    "DownloadError",
    "fetch_wat_paths",
    "download_wat_file",
    "WatDownloader",
    # Parser
    "ParsedEdge",
    "parse_wat_records",
    "parse_rel_flags",
    # Filter
    "DomainFilter",
    "FilterStats",
    # Orchestrator
    "IngestSpec",
    "IngestionResult",
    "IngestionProgress",
    "IngestionSettings",
    "IngestionOrchestrator",
    # Optimized Orchestrator
    "OptimizedIngestionOrchestrator",
    "OptimizedIngestionResult",
    "OptimizedIngestionSettings",
    "OptimizedIngestSpec",
    # Batch Inserter
    "BatchInserter",
    # Checkpoint
    "IngestionCheckpoint",
    # Streaming
    "stream_parse_wat",
    "stream_parse_wat_batched",
    # Parallel Processing
    "ProcessingResult",
    "process_wat_files_parallel",
    # ClickHouse Async
    "ClickHouseAsyncConfig",
    "ClickHouseAsyncStorage",
]
