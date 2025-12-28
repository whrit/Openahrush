"""
Event emission for crawl orchestration.

Emits crawl lifecycle events to Redis for worker consumption.
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


class EventType:
    """Crawl event types."""

    CRAWL_STARTED = "crawl.started"
    CRAWL_PAGE_FETCHED = "crawl.page_fetched"
    CRAWL_HTML_COMPLETE = "crawl.html_complete"
    CRAWL_JS_COMPLETE = "crawl.js_complete"
    CRAWL_COMPLETED = "crawl.completed"
    CRAWL_FAILED = "crawl.failed"


@dataclass
class CrawlEvent:
    """
    Standard event envelope for crawl events.

    Follows the event schema pattern from ARCHITECTURE.md.

    Attributes:
        event_id: Unique identifier for this event.
        event_type: Type of event (e.g., crawl.started).
        occurred_at: When the event occurred.
        project_id: ID of the project.
        crawl_run_id: ID of the crawl run.
        trace_id: Distributed tracing ID.
        payload: Event-specific data.
    """

    event_id: uuid.UUID
    event_type: str
    occurred_at: datetime
    project_id: uuid.UUID
    crawl_run_id: uuid.UUID
    trace_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "project_id": str(self.project_id),
            "crawl_run_id": str(self.crawl_run_id),
            "trace_id": self.trace_id,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        """Serialize event to JSON string."""
        return json.dumps(self.to_dict())


class EventEmitter(Protocol):
    """Protocol for event emission."""

    async def emit(self, event: CrawlEvent) -> None:
        """Emit an event."""
        ...

    async def emit_crawl_started(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        seed_url: str,
        config: dict[str, Any],
    ) -> None:
        """Emit crawl.started event."""
        ...

    async def emit_page_fetched(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        url: str,
        status_code: int,
        response_time_ms: float,
    ) -> None:
        """Emit crawl.page_fetched event."""
        ...

    async def emit_html_complete(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        pages_crawled: int,
    ) -> None:
        """Emit crawl.html_complete event."""
        ...

    async def emit_js_complete(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        pages_rendered: int,
    ) -> None:
        """Emit crawl.js_complete event."""
        ...

    async def emit_crawl_completed(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        pages_crawled: int,
        pages_rendered: int,
        issues_found: int,
        duration_seconds: float,
    ) -> None:
        """Emit crawl.completed event."""
        ...

    async def emit_crawl_failed(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        error_message: str,
    ) -> None:
        """Emit crawl.failed event."""
        ...


class BaseEventEmitter(ABC):
    """Base class for event emitters with common functionality."""

    def __init__(self, trace_id: str | None = None) -> None:
        """Initialize emitter with optional trace ID."""
        self.trace_id = trace_id or str(uuid.uuid4())

    def _create_event(
        self,
        event_type: str,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> CrawlEvent:
        """Create a new event with common fields populated."""
        return CrawlEvent(
            event_id=uuid.uuid4(),
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            project_id=project_id,
            crawl_run_id=crawl_run_id,
            trace_id=self.trace_id,
            payload=payload,
        )

    @abstractmethod
    async def emit(self, event: CrawlEvent) -> None:
        """Emit an event to the underlying transport."""
        ...

    async def emit_crawl_started(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        seed_url: str,
        config: dict[str, Any],
    ) -> None:
        """Emit crawl.started event."""
        event = self._create_event(
            EventType.CRAWL_STARTED,
            project_id,
            crawl_run_id,
            {
                "seed_url": seed_url,
                "config": config,
            },
        )
        await self.emit(event)

    async def emit_page_fetched(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        url: str,
        status_code: int,
        response_time_ms: float,
    ) -> None:
        """Emit crawl.page_fetched event."""
        event = self._create_event(
            EventType.CRAWL_PAGE_FETCHED,
            project_id,
            crawl_run_id,
            {
                "url": url,
                "status_code": status_code,
                "response_time_ms": response_time_ms,
            },
        )
        await self.emit(event)

    async def emit_html_complete(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        pages_crawled: int,
    ) -> None:
        """Emit crawl.html_complete event."""
        event = self._create_event(
            EventType.CRAWL_HTML_COMPLETE,
            project_id,
            crawl_run_id,
            {
                "pages_crawled": pages_crawled,
            },
        )
        await self.emit(event)

    async def emit_js_complete(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        pages_rendered: int,
    ) -> None:
        """Emit crawl.js_complete event."""
        event = self._create_event(
            EventType.CRAWL_JS_COMPLETE,
            project_id,
            crawl_run_id,
            {
                "pages_rendered": pages_rendered,
            },
        )
        await self.emit(event)

    async def emit_crawl_completed(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        pages_crawled: int,
        pages_rendered: int,
        issues_found: int,
        duration_seconds: float,
    ) -> None:
        """Emit crawl.completed event."""
        event = self._create_event(
            EventType.CRAWL_COMPLETED,
            project_id,
            crawl_run_id,
            {
                "pages_crawled": pages_crawled,
                "pages_rendered": pages_rendered,
                "issues_found": issues_found,
                "duration_seconds": duration_seconds,
            },
        )
        await self.emit(event)

    async def emit_crawl_failed(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
        error_message: str,
    ) -> None:
        """Emit crawl.failed event."""
        event = self._create_event(
            EventType.CRAWL_FAILED,
            project_id,
            crawl_run_id,
            {
                "error_message": error_message,
            },
        )
        await self.emit(event)


class RedisEventEmitter(BaseEventEmitter):
    """
    Redis-based event emitter.

    Publishes crawl events to Redis pub/sub channels for consumption
    by other workers and services.
    """

    CHANNEL_PREFIX = "crawl:events"

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

    async def emit(self, event: CrawlEvent) -> None:
        """Publish event to Redis pub/sub channel."""
        channel = self._get_channel(event.event_type)
        await self.redis.publish(channel, event.to_json())

    async def emit_to_stream(
        self,
        event: CrawlEvent,
        stream_key: str = "crawl:events:stream",
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


class NoOpEventEmitter(BaseEventEmitter):
    """
    No-op event emitter for testing.

    Records emitted events for assertion without actual transport.
    """

    def __init__(self, trace_id: str | None = None) -> None:
        """Initialize with empty events list."""
        super().__init__(trace_id)
        self.events: list[CrawlEvent] = []

    async def emit(self, event: CrawlEvent) -> None:
        """Record event without emitting."""
        self.events.append(event)

    def get_events_by_type(self, event_type: str) -> list[CrawlEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def clear(self) -> None:
        """Clear recorded events."""
        self.events.clear()
