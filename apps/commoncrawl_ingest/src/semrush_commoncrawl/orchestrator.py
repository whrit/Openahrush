"""
Ingestion orchestrator for Common Crawl data.

Coordinates the download, parsing, filtering, and storage of
link edges from Common Crawl WAT files.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from semrush_commoncrawl.downloader import WatDownloader, fetch_wat_paths
from semrush_commoncrawl.filter import DomainFilter
from semrush_commoncrawl.parser import Edge, parse_wat_records


class EdgeStorageProtocol(Protocol):
    """Protocol for edge storage backends."""

    async def insert_edges(self, edges: list[Edge]) -> int:
        """
        Insert a batch of edges into storage.

        Args:
            edges: List of Edge objects to store.

        Returns:
            Number of edges successfully inserted.
        """
        ...

    async def get_edge_count(self) -> int:
        """Get the total count of edges in storage."""
        ...


@dataclass
class IngestSpec:
    """
    Specification for an ingestion job.

    Configures filtering, sampling, and limits for a Common Crawl
    ingestion run.

    Attributes:
        target_domains: List of target domains to filter for.
            If None, all external links are ingested.
            Supports wildcard patterns like "*.example.com".
        sample_rate: Random sampling rate (0.0 to 1.0).
            1.0 means no sampling (include all).
        max_edges: Maximum number of edges to ingest.
            None means no limit.
        max_files: Maximum number of WAT files to process.
            None means process all files.
    """

    target_domains: list[str] | None = None
    sample_rate: float = 1.0
    max_edges: int | None = None
    max_files: int | None = None

    def __post_init__(self) -> None:
        """Validate the specification."""
        if not 0.0 <= self.sample_rate <= 1.0:
            raise ValueError("sample_rate must be between 0 and 1")


@dataclass
class IngestionResult:
    """
    Result of an ingestion job.

    Contains statistics and any errors from the ingestion process.

    Attributes:
        edges_ingested: Total number of edges successfully stored.
        files_processed: Number of WAT files processed.
        errors: List of error messages encountered during ingestion.
    """

    edges_ingested: int
    files_processed: int
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Return True if no errors occurred."""
        return len(self.errors) == 0


@dataclass
class IngestionProgress:
    """
    Current progress of an ingestion job.

    Attributes:
        files_processed: Number of WAT files processed so far.
        files_total: Total number of WAT files to process.
        edges_ingested: Number of edges ingested so far.
        is_running: Whether ingestion is currently running.
        current_file: Path of currently processing file.
    """

    files_processed: int = 0
    files_total: int = 0
    edges_ingested: int = 0
    is_running: bool = False
    current_file: str = ""


@dataclass
class IngestionSettings:
    """
    Settings for the ingestion orchestrator.

    Attributes:
        batch_size: Number of edges to batch before storage insert.
        concurrency: Number of concurrent WAT file downloads.
        skip_download_errors: Whether to continue on download errors.
    """

    batch_size: int = 1000
    concurrency: int = 4
    skip_download_errors: bool = True


@dataclass
class IngestionOrchestrator:
    """
    Orchestrates Common Crawl ingestion pipeline.

    Coordinates the full pipeline: downloading WAT files,
    parsing link edges, applying filters, and storing results.

    Attributes:
        storage: Edge storage backend.
        settings: Ingestion settings.
    """

    storage: EdgeStorageProtocol
    settings: IngestionSettings = field(default_factory=IngestionSettings)

    # Internal state
    _progress: IngestionProgress = field(
        default_factory=IngestionProgress, init=False, repr=False
    )

    @property
    def current_progress(self) -> IngestionProgress:
        """Get the current progress of ingestion."""
        return self._progress

    async def ingest_snapshot(
        self,
        snapshot_id: str,
        spec: IngestSpec,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> IngestionResult:
        """
        Ingest link edges from a Common Crawl snapshot.

        Coordinates the full ingestion pipeline:
        1. Fetch list of WAT file paths
        2. Download WAT files (with concurrency control)
        3. Parse WAT records to extract edges
        4. Apply domain and sample rate filtering
        5. Batch insert edges into storage

        Args:
            snapshot_id: Common Crawl snapshot ID (e.g., "CC-MAIN-2024-10").
            spec: Ingestion specification (filters, limits).
            on_progress: Optional callback for progress updates.

        Returns:
            IngestionResult with statistics and any errors.
        """
        # Initialize progress
        self._progress = IngestionProgress(is_running=True)
        errors: list[str] = []
        edges_ingested = 0
        files_processed = 0

        # Create filter
        domain_filter = DomainFilter(
            target_domains=spec.target_domains,
            sample_rate=spec.sample_rate,
        )

        # Create downloader
        downloader = WatDownloader(
            concurrency=self.settings.concurrency,
            skip_errors=self.settings.skip_download_errors,
        )

        # Fetch paths to determine total files
        try:
            all_paths = await fetch_wat_paths(snapshot_id)
            files_to_process = (
                all_paths[: spec.max_files] if spec.max_files else all_paths
            )
            self._progress.files_total = len(files_to_process)
        except Exception as e:
            errors.append(f"Failed to fetch WAT paths: {e}")
            self._progress.is_running = False
            return IngestionResult(
                edges_ingested=0, files_processed=0, errors=errors
            )

        # Edge batch for efficient storage
        edge_batch: list[Edge] = []
        max_edges_reached = False

        # Process files
        try:
            async for path, content in downloader.download_all(
                snapshot_id, limit=spec.max_files
            ):
                if max_edges_reached:
                    break

                self._progress.current_file = path

                try:
                    # Parse WAT content
                    for edge in parse_wat_records(content):
                        # Apply filter
                        if not domain_filter.should_include(edge):
                            continue

                        edge_batch.append(edge)
                        edges_ingested += 1

                        # Check max edges limit
                        if spec.max_edges and edges_ingested >= spec.max_edges:
                            max_edges_reached = True
                            break

                        # Flush batch if full
                        if len(edge_batch) >= self.settings.batch_size:
                            try:
                                await self.storage.insert_edges(edge_batch)
                                edge_batch = []
                            except Exception as e:
                                errors.append(f"Storage error: {e}")
                                edge_batch = []

                except Exception as e:
                    errors.append(f"Parse error for {path}: {e}")

                files_processed += 1
                self._progress.files_processed = files_processed
                self._progress.edges_ingested = edges_ingested

                # Progress callback
                if on_progress:
                    on_progress({
                        "files_processed": files_processed,
                        "files_total": self._progress.files_total,
                        "edges_ingested": edges_ingested,
                        "current_file": path,
                    })

        except Exception as e:
            errors.append(f"Download error: {e}")

        # Collect download errors from downloader
        errors.extend(downloader.errors)

        # Flush remaining edges
        if edge_batch:
            try:
                await self.storage.insert_edges(edge_batch)
            except Exception as e:
                errors.append(f"Storage error: {e}")

        self._progress.is_running = False

        return IngestionResult(
            edges_ingested=edges_ingested,
            files_processed=files_processed,
            errors=errors,
        )
