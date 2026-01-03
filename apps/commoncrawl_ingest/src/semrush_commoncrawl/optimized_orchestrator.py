"""
Optimized ingestion orchestrator for high-performance Common Crawl processing.

Integrates parallel WAT file processing, streaming parsing, batch inserts,
and checkpoint-based resumability for scalable ingestion.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from semrush_commoncrawl.batch_inserter import BatchInserter
from semrush_commoncrawl.checkpoint import IngestionCheckpoint
from semrush_commoncrawl.downloader import fetch_wat_paths
from semrush_commoncrawl.events import (
    BaseCommonCrawlEventEmitter,
    NoOpCommonCrawlEventEmitter,
)
from semrush_commoncrawl.filter import DomainFilter
from semrush_commoncrawl.parallel import process_wat_files_parallel
from semrush_commoncrawl.storage.base import Edge
from semrush_commoncrawl.streaming import stream_parse_wat


class EdgeStorageProtocol(Protocol):
    """Protocol for edge storage backends."""

    async def insert_edges(self, edges: list[Edge]) -> int:
        """Insert a batch of edges into storage."""
        ...

    async def get_edge_count(self) -> int:
        """Get the total count of edges in storage."""
        ...


class WatDownloaderProtocol(Protocol):
    """Protocol for WAT file downloaders."""

    async def download(self, path: str) -> bytes:
        """Download a WAT file by path."""
        ...


@dataclass
class OptimizedIngestSpec:
    """
    Specification for an optimized ingestion job.

    Attributes:
        target_domains: List of target domains to filter for.
        sample_rate: Random sampling rate (0.0 to 1.0).
        max_edges: Maximum number of edges to ingest.
        max_files: Maximum number of WAT files to process.
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
class OptimizedIngestionResult:
    """
    Result of an optimized ingestion job.

    Attributes:
        edges_ingested: Total number of edges successfully stored.
        files_processed: Number of WAT files processed.
        files_skipped: Number of files skipped (already completed).
        errors: List of error messages encountered.
        duration_seconds: Total processing time.
    """

    edges_ingested: int
    files_processed: int
    files_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def success(self) -> bool:
        """Return True if no errors occurred."""
        return len(self.errors) == 0


@dataclass
class OptimizedIngestionSettings:
    """
    Settings for the optimized ingestion orchestrator.

    Attributes:
        batch_size: Number of edges to batch before storage insert (default 10000).
        concurrency: Number of concurrent WAT file downloads.
        checkpoint_interval: Number of files between checkpoint saves.
        skip_download_errors: Whether to continue on download errors.
    """

    batch_size: int = 10000
    concurrency: int = 8
    checkpoint_interval: int = 10
    skip_download_errors: bool = True


@dataclass
class OptimizedIngestionOrchestrator:
    """
    Optimized orchestrator for high-performance Common Crawl ingestion.

    Features:
    - Parallel WAT file processing with configurable concurrency
    - Streaming WAT parsing to minimize memory usage
    - Batch inserts (10K+ rows) for efficient storage
    - Checkpoint-based resumability for interrupted jobs

    Attributes:
        storage: Edge storage backend.
        downloader: WAT file downloader.
        settings: Ingestion settings.
        checkpoint: Optional checkpoint for resumability.
        event_emitter: Event emitter for lifecycle events.
        project_id: Optional project ID for scoped ingestion.
    """

    storage: EdgeStorageProtocol
    downloader: WatDownloaderProtocol
    settings: OptimizedIngestionSettings = field(default_factory=OptimizedIngestionSettings)
    checkpoint: IngestionCheckpoint | None = None
    event_emitter: BaseCommonCrawlEventEmitter = field(default_factory=NoOpCommonCrawlEventEmitter)
    project_id: uuid.UUID | None = None

    async def ingest_snapshot(
        self,
        snapshot_id: str,
        spec: OptimizedIngestSpec,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> OptimizedIngestionResult:
        """
        Ingest link edges from a Common Crawl snapshot with optimizations.

        Features:
        1. Parallel WAT file downloads with semaphore-based concurrency
        2. Streaming WAT parsing (memory efficient)
        3. Batch inserts (10K+ rows per insert)
        4. Checkpoint-based resume for interrupted jobs

        Args:
            snapshot_id: Common Crawl snapshot ID (e.g., "CC-MAIN-2024-10").
            spec: Ingestion specification (filters, limits).
            on_progress: Optional callback for progress updates.

        Returns:
            OptimizedIngestionResult with statistics and any errors.
        """
        start_time = time.monotonic()
        errors: list[str] = []
        edges_ingested = 0
        files_processed = 0
        files_skipped = 0

        # Emit ingest requested event
        await self.event_emitter.emit_ingest_requested(
            snapshot_id=snapshot_id,
            target_domains=spec.target_domains,
            sample_rate=spec.sample_rate,
            max_edges=spec.max_edges,
            max_files=spec.max_files,
            project_id=self.project_id,
        )

        # Create filter
        domain_filter = DomainFilter(
            target_domains=spec.target_domains,
            sample_rate=spec.sample_rate,
        )

        # Fetch all WAT file paths
        try:
            all_paths = await fetch_wat_paths(snapshot_id)
            files_to_process = all_paths[: spec.max_files] if spec.max_files else all_paths
        except Exception as e:
            error_msg = f"Failed to fetch WAT paths: {e}"
            errors.append(error_msg)
            await self.event_emitter.emit_ingest_failed(
                snapshot_id=snapshot_id,
                error=error_msg,
                files_processed=0,
                edges_ingested=0,
                project_id=self.project_id,
            )
            return OptimizedIngestionResult(
                edges_ingested=0,
                files_processed=0,
                errors=errors,
                duration_seconds=time.monotonic() - start_time,
            )

        # Filter out already-completed files if checkpoint is available
        if self.checkpoint:
            pending_files = await self.checkpoint.get_pending_files(files_to_process)
            files_skipped = len(files_to_process) - len(pending_files)
            files_to_process = pending_files

            # Load previous progress
            progress = await self.checkpoint.get_progress()
            if progress:
                edges_ingested = progress.get("edges_ingested", 0)
                files_processed = progress.get("files_processed", 0)

        total_files = len(files_to_process) + files_skipped
        max_edges_reached = False

        # Use batch inserter for efficient storage
        async with BatchInserter(
            storage=self.storage,
            batch_size=self.settings.batch_size,
        ) as inserter:

            # Process files in parallel
            async for result in process_wat_files_parallel(
                paths=files_to_process,
                download_fn=self.downloader.download,
                concurrency=self.settings.concurrency,
            ):
                if max_edges_reached:
                    break

                if not result.success:
                    if not self.settings.skip_download_errors:
                        errors.append(f"Download error for {result.path}: {result.error}")
                    continue

                # Stream parse the WAT content
                try:
                    async for edge in stream_parse_wat(
                        content=result.content or b"",
                        snapshot_id=snapshot_id,
                    ):
                        # Apply domain filter
                        if not domain_filter.should_include(edge):
                            continue

                        # Add edge to batch
                        await inserter.add(edge)
                        edges_ingested += 1

                        # Check max edges limit
                        if spec.max_edges and edges_ingested >= spec.max_edges:
                            max_edges_reached = True
                            break

                except Exception as e:
                    errors.append(f"Parse error for {result.path}: {e}")

                files_processed += 1

                # Mark file complete in checkpoint
                if self.checkpoint:
                    await self.checkpoint.mark_file_complete(result.path)

                    # Save progress periodically
                    if files_processed % self.settings.checkpoint_interval == 0:
                        await self.checkpoint.save_progress(
                            files_processed=files_processed,
                            edges_ingested=edges_ingested,
                            current_file=result.path,
                        )

                # Progress callback
                if on_progress:
                    on_progress({
                        "files_processed": files_processed,
                        "files_total": total_files,
                        "files_skipped": files_skipped,
                        "edges_ingested": edges_ingested,
                        "current_file": result.path,
                    })

        # Final checkpoint save
        if self.checkpoint:
            await self.checkpoint.save_progress(
                files_processed=files_processed,
                edges_ingested=edges_ingested,
            )

        duration_seconds = time.monotonic() - start_time

        # Emit completion event
        await self.event_emitter.emit_ingest_completed(
            snapshot_id=snapshot_id,
            files_processed=files_processed,
            edges_ingested=edges_ingested,
            duration_seconds=duration_seconds,
            errors=errors if errors else None,
            project_id=self.project_id,
        )

        return OptimizedIngestionResult(
            edges_ingested=edges_ingested,
            files_processed=files_processed,
            files_skipped=files_skipped,
            errors=errors,
            duration_seconds=duration_seconds,
        )
