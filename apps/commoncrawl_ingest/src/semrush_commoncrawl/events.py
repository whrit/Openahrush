"""
Event emission for Common Crawl ingestion operations.

Emits ingestion lifecycle events to Redis for worker consumption.
Events follow the standard envelope format defined in ARCHITECTURE.md.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from redis.asyncio import Redis


class CommonCrawlEventType:
    """Common Crawl ingestion event types."""

    INGEST_REQUESTED = "commoncrawl.ingest_requested"
    INGEST_PROGRESS = "commoncrawl.ingest_progress"
    INGEST_COMPLETED = "commoncrawl.ingest_completed"
    INGEST_FAILED = "commoncrawl.ingest_failed"


@dataclass
class CommonCrawlEvent:
    """
    Standard event envelope for Common Crawl events.

    Follows the event schema pattern from ARCHITECTURE.md Section 7.1.

    Attributes:
        event_id: Unique identifier for this event.
        event_type: Type of event (e.g., commoncrawl.ingest_requested).
        occurred_at: When the event occurred.
        project_id: ID of the project (may be None for global ingestion).
        trace_id: Distributed tracing ID.
        payload: Event-specific data.
    """

    event_id: uuid.UUID
    event_type: str
    occurred_at: datetime
    project_id: uuid.UUID | None
    trace_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "project_id": str(self.project_id) if self.project_id else None,
            "trace_id": self.trace_id,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        """Serialize event to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class IngestPayload:
    """
    Payload data for Common Crawl ingestion events.

    Attributes:
        snapshot_id: Common Crawl snapshot ID (e.g., CC-MAIN-2024-10).
        target_domains: List of target domains being ingested.
        sample_rate: Sampling rate applied (0.0-1.0).
        max_edges: Maximum edges limit if set.
        max_files: Maximum files limit if set.
        files_processed: Number of WAT files processed.
        files_total: Total number of WAT files to process.
        edges_ingested: Number of edges ingested.
        current_file: Currently processing file path.
        error: Error message (for failed events).
        errors: List of non-fatal errors encountered.
        duration_seconds: Total duration of ingestion.
    """

    snapshot_id: str
    target_domains: list[str] | None = None
    sample_rate: float = 1.0
    max_edges: int | None = None
    max_files: int | None = None
    files_processed: int = 0
    files_total: int = 0
    edges_ingested: int = 0
    current_file: str | None = None
    error: str | None = None
    errors: list[str] | None = None
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dictionary for serialization."""
        result: dict[str, Any] = {
            "snapshot_id": self.snapshot_id,
            "sample_rate": self.sample_rate,
        }
        if self.target_domains is not None:
            result["target_domains"] = self.target_domains
        if self.max_edges is not None:
            result["max_edges"] = self.max_edges
        if self.max_files is not None:
            result["max_files"] = self.max_files
        if self.files_processed > 0:
            result["files_processed"] = self.files_processed
        if self.files_total > 0:
            result["files_total"] = self.files_total
        if self.edges_ingested > 0:
            result["edges_ingested"] = self.edges_ingested
        if self.current_file is not None:
            result["current_file"] = self.current_file
        if self.error is not None:
            result["error"] = self.error
        if self.errors is not None and len(self.errors) > 0:
            result["errors"] = self.errors
        if self.duration_seconds is not None:
            result["duration_seconds"] = self.duration_seconds
        return result


class CommonCrawlEventEmitter(Protocol):
    """Protocol for Common Crawl event emission."""

    async def emit(self, event: CommonCrawlEvent) -> None:
        """Emit an event."""
        ...

    async def emit_ingest_requested(
        self,
        snapshot_id: str,
        target_domains: list[str] | None = None,
        sample_rate: float = 1.0,
        max_edges: int | None = None,
        max_files: int | None = None,
        project_id: uuid.UUID | None = None,
    ) -> None:
        """Emit commoncrawl.ingest_requested event."""
        ...

    async def emit_ingest_progress(
        self,
        snapshot_id: str,
        files_processed: int,
        files_total: int,
        edges_ingested: int,
        current_file: str | None = None,
        project_id: uuid.UUID | None = None,
    ) -> None:
        """Emit commoncrawl.ingest_progress event."""
        ...

    async def emit_ingest_completed(
        self,
        snapshot_id: str,
        files_processed: int,
        edges_ingested: int,
        duration_seconds: float,
        errors: list[str] | None = None,
        project_id: uuid.UUID | None = None,
    ) -> None:
        """Emit commoncrawl.ingest_completed event."""
        ...

    async def emit_ingest_failed(
        self,
        snapshot_id: str,
        error: str,
        files_processed: int = 0,
        edges_ingested: int = 0,
        project_id: uuid.UUID | None = None,
    ) -> None:
        """Emit commoncrawl.ingest_failed event."""
        ...


class BaseCommonCrawlEventEmitter(ABC):
    """Base class for Common Crawl event emitters with common functionality."""

    def __init__(self, trace_id: str | None = None) -> None:
        """Initialize emitter with optional trace ID."""
        self.trace_id = trace_id or str(uuid.uuid4())

    def _create_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        project_id: uuid.UUID | None = None,
    ) -> CommonCrawlEvent:
        """Create a new event with common fields populated."""
        return CommonCrawlEvent(
            event_id=uuid.uuid4(),
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            project_id=project_id,
            trace_id=self.trace_id,
            payload=payload,
        )

    @abstractmethod
    async def emit(self, event: CommonCrawlEvent) -> None:
        """Emit an event to the underlying transport."""
        ...

    async def emit_ingest_requested(
        self,
        snapshot_id: str,
        target_domains: list[str] | None = None,
        sample_rate: float = 1.0,
        max_edges: int | None = None,
        max_files: int | None = None,
        project_id: uuid.UUID | None = None,
    ) -> None:
        """Emit commoncrawl.ingest_requested event."""
        payload = IngestPayload(
            snapshot_id=snapshot_id,
            target_domains=target_domains,
            sample_rate=sample_rate,
            max_edges=max_edges,
            max_files=max_files,
        )
        event = self._create_event(
            CommonCrawlEventType.INGEST_REQUESTED,
            payload.to_dict(),
            project_id,
        )
        await self.emit(event)

    async def emit_ingest_progress(
        self,
        snapshot_id: str,
        files_processed: int,
        files_total: int,
        edges_ingested: int,
        current_file: str | None = None,
        project_id: uuid.UUID | None = None,
    ) -> None:
        """Emit commoncrawl.ingest_progress event."""
        payload = IngestPayload(
            snapshot_id=snapshot_id,
            files_processed=files_processed,
            files_total=files_total,
            edges_ingested=edges_ingested,
            current_file=current_file,
        )
        event = self._create_event(
            CommonCrawlEventType.INGEST_PROGRESS,
            payload.to_dict(),
            project_id,
        )
        await self.emit(event)

    async def emit_ingest_completed(
        self,
        snapshot_id: str,
        files_processed: int,
        edges_ingested: int,
        duration_seconds: float,
        errors: list[str] | None = None,
        project_id: uuid.UUID | None = None,
    ) -> None:
        """Emit commoncrawl.ingest_completed event."""
        payload = IngestPayload(
            snapshot_id=snapshot_id,
            files_processed=files_processed,
            edges_ingested=edges_ingested,
            duration_seconds=duration_seconds,
            errors=errors,
        )
        event = self._create_event(
            CommonCrawlEventType.INGEST_COMPLETED,
            payload.to_dict(),
            project_id,
        )
        await self.emit(event)

    async def emit_ingest_failed(
        self,
        snapshot_id: str,
        error: str,
        files_processed: int = 0,
        edges_ingested: int = 0,
        project_id: uuid.UUID | None = None,
    ) -> None:
        """Emit commoncrawl.ingest_failed event."""
        payload = IngestPayload(
            snapshot_id=snapshot_id,
            files_processed=files_processed,
            edges_ingested=edges_ingested,
            error=error,
        )
        event = self._create_event(
            CommonCrawlEventType.INGEST_FAILED,
            payload.to_dict(),
            project_id,
        )
        await self.emit(event)


class RedisCommonCrawlEventEmitter(BaseCommonCrawlEventEmitter):
    """
    Redis-based event emitter for Common Crawl events.

    Publishes ingestion events to Redis pub/sub channels for consumption
    by other workers and services.
    """

    CHANNEL_PREFIX = "commoncrawl:events"

    def __init__(
        self,
        redis: Redis,
        trace_id: str | None = None,
    ) -> None:
        """
        Initialize Redis event emitter.

        Args:
            redis: Async Redis client.
            trace_id: Optional trace ID for distributed tracing.
        """
        super().__init__(trace_id)
        self.redis = redis

    def _get_channel(self, event_type: str) -> str:
        """Get the Redis channel for an event type."""
        return f"{self.CHANNEL_PREFIX}:{event_type}"

    async def emit(self, event: CommonCrawlEvent) -> None:
        """Publish event to Redis pub/sub channel."""
        channel = self._get_channel(event.event_type)
        await self.redis.publish(channel, event.to_json())

    async def emit_to_stream(
        self,
        event: CommonCrawlEvent,
        stream_key: str = "commoncrawl:events:stream",
    ) -> str:
        """
        Add event to Redis stream for durable messaging.

        Returns:
            The stream entry ID.
        """
        result = await self.redis.xadd(
            stream_key,
            {
                "event_type": event.event_type,
                "data": event.to_json(),
            },
        )
        # Redis returns bytes or str depending on decode_responses setting
        return result if isinstance(result, str) else result.decode()


class NoOpCommonCrawlEventEmitter(BaseCommonCrawlEventEmitter):
    """
    No-op event emitter for testing.

    Records emitted events for assertion without actual transport.
    """

    def __init__(self, trace_id: str | None = None) -> None:
        """Initialize with empty events list."""
        super().__init__(trace_id)
        self.events: list[CommonCrawlEvent] = []

    async def emit(self, event: CommonCrawlEvent) -> None:
        """Record event without emitting."""
        self.events.append(event)

    def get_events_by_type(self, event_type: str) -> list[CommonCrawlEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def clear(self) -> None:
        """Clear recorded events."""
        self.events.clear()
