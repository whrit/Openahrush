"""
Event emission for integration sync operations.

Emits integration lifecycle events to Redis for worker consumption.
Events follow the standard envelope format defined in ARCHITECTURE.md.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Protocol

from redis.asyncio import Redis


class IntegrationEventType:
    """Integration sync event types."""

    SYNC_REQUESTED = "integration.sync_requested"
    SYNC_PROGRESS = "integration.sync_progress"
    SYNC_COMPLETED = "integration.sync_completed"
    SYNC_FAILED = "integration.sync_failed"


@dataclass
class IntegrationEvent:
    """
    Standard event envelope for integration events.

    Follows the event schema pattern from ARCHITECTURE.md Section 7.1.

    Attributes:
        event_id: Unique identifier for this event.
        event_type: Type of event (e.g., integration.sync_requested).
        occurred_at: When the event occurred.
        project_id: ID of the project.
        trace_id: Distributed tracing ID.
        payload: Event-specific data.
    """

    event_id: uuid.UUID
    event_type: str
    occurred_at: datetime
    project_id: uuid.UUID
    trace_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "project_id": str(self.project_id),
            "trace_id": self.trace_id,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        """Serialize event to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class SyncPayload:
    """
    Payload data for integration sync events.

    Contains all fields specified in ARCHITECTURE.md Section 7.2.

    Attributes:
        provider: Integration provider name (e.g., google_search_console).
        integration_account_id: UUID of the integration account.
        property_id: Provider property identifier.
        date_range_start: Start of the sync date range.
        date_range_end: End of the sync date range.
        mode: Sync mode (backfill, incremental).
        records_written: Number of records written (for completed events).
        error: Error message (for failed events).
        progress_percent: Progress percentage (for progress events).
    """

    provider: str
    integration_account_id: uuid.UUID
    property_id: str
    date_range_start: date | None = None
    date_range_end: date | None = None
    mode: str = "incremental"
    records_written: int | None = None
    error: str | None = None
    progress_percent: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dictionary for serialization."""
        result: dict[str, Any] = {
            "provider": self.provider,
            "integration_account_id": str(self.integration_account_id),
            "property_id": self.property_id,
            "mode": self.mode,
        }
        if self.date_range_start:
            result["date_range_start"] = self.date_range_start.isoformat()
        if self.date_range_end:
            result["date_range_end"] = self.date_range_end.isoformat()
        if self.records_written is not None:
            result["records_written"] = self.records_written
        if self.error is not None:
            result["error"] = self.error
        if self.progress_percent is not None:
            result["progress_percent"] = self.progress_percent
        return result


class IntegrationEventEmitter(Protocol):
    """Protocol for integration event emission."""

    async def emit(self, event: IntegrationEvent) -> None:
        """Emit an event."""
        ...

    async def emit_sync_requested(
        self,
        project_id: uuid.UUID,
        provider: str,
        integration_account_id: uuid.UUID,
        property_id: str,
        date_range_start: date,
        date_range_end: date,
        mode: str = "incremental",
    ) -> None:
        """Emit integration.sync_requested event."""
        ...

    async def emit_sync_progress(
        self,
        project_id: uuid.UUID,
        provider: str,
        integration_account_id: uuid.UUID,
        property_id: str,
        progress_percent: float,
    ) -> None:
        """Emit integration.sync_progress event."""
        ...

    async def emit_sync_completed(
        self,
        project_id: uuid.UUID,
        provider: str,
        integration_account_id: uuid.UUID,
        property_id: str,
        date_range_start: date,
        date_range_end: date,
        mode: str,
        records_written: int,
    ) -> None:
        """Emit integration.sync_completed event."""
        ...

    async def emit_sync_failed(
        self,
        project_id: uuid.UUID,
        provider: str,
        integration_account_id: uuid.UUID,
        property_id: str,
        error: str,
    ) -> None:
        """Emit integration.sync_failed event."""
        ...


class BaseIntegrationEventEmitter(ABC):
    """Base class for integration event emitters with common functionality."""

    def __init__(self, trace_id: str | None = None) -> None:
        """Initialize emitter with optional trace ID."""
        self.trace_id = trace_id or str(uuid.uuid4())

    def _create_event(
        self,
        event_type: str,
        project_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> IntegrationEvent:
        """Create a new event with common fields populated."""
        return IntegrationEvent(
            event_id=uuid.uuid4(),
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            project_id=project_id,
            trace_id=self.trace_id,
            payload=payload,
        )

    @abstractmethod
    async def emit(self, event: IntegrationEvent) -> None:
        """Emit an event to the underlying transport."""
        ...

    async def emit_sync_requested(
        self,
        project_id: uuid.UUID,
        provider: str,
        integration_account_id: uuid.UUID,
        property_id: str,
        date_range_start: date,
        date_range_end: date,
        mode: str = "incremental",
    ) -> None:
        """Emit integration.sync_requested event."""
        payload = SyncPayload(
            provider=provider,
            integration_account_id=integration_account_id,
            property_id=property_id,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            mode=mode,
        )
        event = self._create_event(
            IntegrationEventType.SYNC_REQUESTED,
            project_id,
            payload.to_dict(),
        )
        await self.emit(event)

    async def emit_sync_progress(
        self,
        project_id: uuid.UUID,
        provider: str,
        integration_account_id: uuid.UUID,
        property_id: str,
        progress_percent: float,
    ) -> None:
        """Emit integration.sync_progress event."""
        payload = SyncPayload(
            provider=provider,
            integration_account_id=integration_account_id,
            property_id=property_id,
            progress_percent=progress_percent,
        )
        event = self._create_event(
            IntegrationEventType.SYNC_PROGRESS,
            project_id,
            payload.to_dict(),
        )
        await self.emit(event)

    async def emit_sync_completed(
        self,
        project_id: uuid.UUID,
        provider: str,
        integration_account_id: uuid.UUID,
        property_id: str,
        date_range_start: date,
        date_range_end: date,
        mode: str,
        records_written: int,
    ) -> None:
        """Emit integration.sync_completed event."""
        payload = SyncPayload(
            provider=provider,
            integration_account_id=integration_account_id,
            property_id=property_id,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            mode=mode,
            records_written=records_written,
        )
        event = self._create_event(
            IntegrationEventType.SYNC_COMPLETED,
            project_id,
            payload.to_dict(),
        )
        await self.emit(event)

    async def emit_sync_failed(
        self,
        project_id: uuid.UUID,
        provider: str,
        integration_account_id: uuid.UUID,
        property_id: str,
        error: str,
    ) -> None:
        """Emit integration.sync_failed event."""
        payload = SyncPayload(
            provider=provider,
            integration_account_id=integration_account_id,
            property_id=property_id,
            error=error,
        )
        event = self._create_event(
            IntegrationEventType.SYNC_FAILED,
            project_id,
            payload.to_dict(),
        )
        await self.emit(event)


class RedisIntegrationEventEmitter(BaseIntegrationEventEmitter):
    """
    Redis-based event emitter for integration events.

    Publishes integration events to Redis pub/sub channels for consumption
    by other workers and services.
    """

    CHANNEL_PREFIX = "integration:events"

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

    async def emit(self, event: IntegrationEvent) -> None:
        """Publish event to Redis pub/sub channel."""
        channel = self._get_channel(event.event_type)
        await self.redis.publish(channel, event.to_json())

    async def emit_to_stream(
        self,
        event: IntegrationEvent,
        stream_key: str = "integration:events:stream",
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


class NoOpIntegrationEventEmitter(BaseIntegrationEventEmitter):
    """
    No-op event emitter for testing.

    Records emitted events for assertion without actual transport.
    """

    def __init__(self, trace_id: str | None = None) -> None:
        """Initialize with empty events list."""
        super().__init__(trace_id)
        self.events: list[IntegrationEvent] = []

    async def emit(self, event: IntegrationEvent) -> None:
        """Record event without emitting."""
        self.events.append(event)

    def get_events_by_type(self, event_type: str) -> list[IntegrationEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def clear(self) -> None:
        """Clear recorded events."""
        self.events.clear()
