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

Note: This is a placeholder package. Full implementation pending.
See COMMONCRAWL_INGESTION.md for detailed design.
"""

__version__ = "0.1.0"

from enum import StrEnum


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
