"""
Batch inserter for efficient edge storage.

Provides batched inserts with configurable batch size and auto-flush
for high-throughput Common Crawl edge ingestion.
"""

from __future__ import annotations

from typing import Any, Protocol

from semrush_commoncrawl.storage.base import Edge


class EdgeStorageProtocol(Protocol):
    """Protocol for edge storage backends."""

    async def insert_edges(self, edges: list[Edge]) -> int:
        """Insert a batch of edges into storage."""
        ...


class BatchInserter:
    """
    Batched edge inserter with configurable batch size and auto-flush.

    Accumulates edges in a buffer and flushes to storage when the batch
    size is reached or when explicitly flushed.

    Attributes:
        storage: The underlying edge storage backend.
        batch_size: Number of edges to accumulate before auto-flush.
        flush_interval: Time interval for periodic flush (seconds).
    """

    def __init__(
        self,
        storage: EdgeStorageProtocol,
        batch_size: int = 10000,
        flush_interval: float = 5.0,
    ) -> None:
        """
        Initialize the batch inserter.

        Args:
            storage: Edge storage backend implementing insert_edges.
            batch_size: Number of edges to batch before auto-flush.
            flush_interval: Flush interval in seconds (for future use).
        """
        self.storage = storage
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._buffer: list[Edge] = []
        self._total_inserted = 0
        self._flush_count = 0

    @property
    def pending_count(self) -> int:
        """Number of edges waiting to be flushed."""
        return len(self._buffer)

    @property
    def total_inserted(self) -> int:
        """Total number of edges inserted so far."""
        return self._total_inserted

    @property
    def flush_count(self) -> int:
        """Number of flush operations performed."""
        return self._flush_count

    async def add(self, edge: Edge) -> None:
        """
        Add a single edge to the batch.

        If the batch size is reached, automatically flushes to storage.

        Args:
            edge: Edge to add to the batch.
        """
        self._buffer.append(edge)
        if len(self._buffer) >= self.batch_size:
            await self.flush()

    async def add_batch(self, edges: list[Edge]) -> None:
        """
        Add multiple edges to the batch.

        May trigger multiple flushes if edges exceed batch size.

        Args:
            edges: List of edges to add.
        """
        for edge in edges:
            await self.add(edge)

    async def flush(self) -> None:
        """
        Flush all pending edges to storage.

        Does nothing if the buffer is empty.
        """
        if not self._buffer:
            return

        count = await self.storage.insert_edges(self._buffer)
        self._total_inserted += count
        self._flush_count += 1
        self._buffer = []

    def get_stats(self) -> dict[str, Any]:
        """
        Get insertion statistics.

        Returns:
            Dictionary containing batch inserter statistics.
        """
        return {
            "total_inserted": self._total_inserted,
            "pending_count": self.pending_count,
            "flush_count": self._flush_count,
            "batch_size": self.batch_size,
        }

    async def __aenter__(self) -> BatchInserter:
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context, flushing any remaining edges."""
        await self.flush()
