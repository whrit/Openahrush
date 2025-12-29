"""
Webhooks API endpoints.

Provides endpoints for:
- POST /projects/{project_id}/webhooks - Create webhook config
- GET /projects/{project_id}/webhooks - List webhook configs
- GET /projects/{project_id}/webhooks/{webhook_id} - Get webhook config
- PATCH /projects/{project_id}/webhooks/{webhook_id} - Update webhook config
- DELETE /projects/{project_id}/webhooks/{webhook_id} - Delete webhook config
- GET /projects/{project_id}/webhooks/{webhook_id}/deliveries - Delivery history
- POST /projects/{project_id}/webhooks/{webhook_id}/test - Send test event
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl
from semrush_core.models import (
    VALID_WEBHOOK_EVENTS,
    DeliveryStatus,
    WebhookConfig,
    WebhookDelivery,
)
from semrush_core.security.encryption import (
    encrypt_token,
    generate_secure_token,
)
from sqlalchemy import func, select

from semrush_api.deps import CurrentUser, DbSession, Pagination, UserProject

router = APIRouter(prefix="/projects", tags=["Webhooks"])


# =============================================================================
# Schemas
# =============================================================================


class WebhookCreate(BaseModel):
    """Request body for creating a webhook configuration."""

    url: HttpUrl = Field(..., description="Webhook endpoint URL (must be HTTPS in production)")
    enabled_events: list[str] = Field(
        ...,
        min_length=1,
        description="List of event types to subscribe to",
    )
    is_enabled: bool = Field(default=True, description="Whether the webhook is active")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://example.com/webhooks",
                    "enabled_events": ["crawl.completed", "alert.fired"],
                    "is_enabled": True,
                }
            ]
        }
    }


class WebhookUpdate(BaseModel):
    """Request body for updating a webhook configuration."""

    url: HttpUrl | None = Field(None, description="New webhook endpoint URL")
    enabled_events: list[str] | None = Field(
        None,
        min_length=1,
        description="New list of event types to subscribe to",
    )
    is_enabled: bool | None = Field(None, description="Whether the webhook is active")
    regenerate_secret: bool = Field(
        default=False,
        description="If true, generate a new signing secret",
    )


class WebhookResponse(BaseModel):
    """Response schema for a webhook configuration."""

    id: str
    project_id: str
    url: str
    enabled_events: list[str]
    is_enabled: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class WebhookWithSecretResponse(BaseModel):
    """Response schema for webhook with secret (only on create or regenerate)."""

    id: str
    project_id: str
    url: str
    secret: str  # Only returned on create or regenerate
    enabled_events: list[str]
    is_enabled: bool
    created_at: str
    updated_at: str


class WebhookList(BaseModel):
    """Response schema for list of webhooks."""

    items: list[WebhookResponse]
    total: int
    page: int
    page_size: int


class WebhookDeliveryResponse(BaseModel):
    """Response schema for a webhook delivery record."""

    id: str
    webhook_config_id: str
    event_type: str
    delivery_status: str
    attempts: int
    last_attempt_at: str | None
    response_status: int | None
    response_body: str | None
    next_retry_at: str | None
    created_at: str


class WebhookDeliveryList(BaseModel):
    """Response schema for list of webhook deliveries."""

    items: list[WebhookDeliveryResponse]
    total: int
    page: int
    page_size: int


class WebhookTestRequest(BaseModel):
    """Request body for testing a webhook."""

    event_type: str = Field(
        default="test.ping",
        description="Event type to send (default: test.ping)",
    )


class WebhookTestResponse(BaseModel):
    """Response schema for webhook test result."""

    delivery_id: str
    status: str
    message: str


class ValidEventsResponse(BaseModel):
    """Response schema for list of valid webhook events."""

    events: list[str]


# =============================================================================
# Helper functions
# =============================================================================


async def get_webhook_config(
    db: DbSession,
    project_id: uuid.UUID,
    webhook_id: uuid.UUID,
) -> WebhookConfig:
    """
    Get a webhook configuration by ID.

    Args:
        db: Database session.
        project_id: Project UUID.
        webhook_id: Webhook config UUID.

    Returns:
        WebhookConfig if found.

    Raises:
        HTTPException: 404 if webhook not found.
    """
    result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.id == webhook_id,
            WebhookConfig.project_id == project_id,
        )
    )
    webhook = result.scalar_one_or_none()

    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook configuration not found",
        )

    return webhook


def validate_events(events: list[str]) -> None:
    """
    Validate that all event types are valid.

    Args:
        events: List of event types to validate.

    Raises:
        HTTPException: 400 if any event type is invalid.
    """
    # Allow test.ping for testing
    valid_events = set(VALID_WEBHOOK_EVENTS) | {"test.ping"}
    invalid = set(events) - valid_events

    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event types: {', '.join(sorted(invalid))}. "
            f"Valid events: {', '.join(sorted(VALID_WEBHOOK_EVENTS))}",
        )


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/webhooks/events",
    response_model=ValidEventsResponse,
    status_code=status.HTTP_200_OK,
    summary="List valid webhook events",
    description="Get a list of all valid webhook event types.",
)
async def list_valid_events() -> ValidEventsResponse:
    """
    List all valid webhook event types.

    Returns:
        List of valid event types.
    """
    return ValidEventsResponse(events=VALID_WEBHOOK_EVENTS)


@router.post(
    "/{project_id}/webhooks",
    response_model=WebhookWithSecretResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook",
    description="Create a new webhook configuration for a project. "
    "The secret is returned only once on creation.",
)
async def create_webhook(
    project: UserProject,
    data: WebhookCreate,
    db: DbSession,
) -> WebhookWithSecretResponse:
    """
    Create a new webhook configuration.

    Args:
        project: Validated project owned by current user.
        data: Webhook creation data.
        db: Database session.

    Returns:
        Created webhook configuration with secret.
    """
    # Validate event types
    validate_events(data.enabled_events)

    # Generate a secure secret
    secret = generate_secure_token(32)

    # Create webhook config with encrypted secret
    webhook = WebhookConfig(
        project_id=project.id,
        url=str(data.url),
        secret=encrypt_token(secret),
        enabled_events=data.enabled_events,
        is_enabled=data.is_enabled,
    )

    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    return WebhookWithSecretResponse(
        id=str(webhook.id),
        project_id=str(webhook.project_id),
        url=webhook.url,
        secret=secret,  # Return the plaintext secret once
        enabled_events=webhook.enabled_events,
        is_enabled=webhook.is_enabled,
        created_at=webhook.created_at.isoformat(),
        updated_at=webhook.updated_at.isoformat(),
    )


@router.get(
    "/{project_id}/webhooks",
    response_model=WebhookList,
    status_code=status.HTTP_200_OK,
    summary="List webhooks",
    description="List all webhook configurations for a project.",
)
async def list_webhooks(
    project: UserProject,
    db: DbSession,
    pagination: Pagination,
) -> WebhookList:
    """
    List all webhook configurations for a project.

    Args:
        project: Validated project owned by current user.
        db: Database session.
        pagination: Pagination parameters.

    Returns:
        Paginated list of webhook configurations.
    """
    # Get total count
    count_result = await db.execute(
        select(func.count(WebhookConfig.id)).where(WebhookConfig.project_id == project.id)
    )
    total = count_result.scalar() or 0

    # Get paginated webhooks
    result = await db.execute(
        select(WebhookConfig)
        .where(WebhookConfig.project_id == project.id)
        .order_by(WebhookConfig.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    webhooks = result.scalars().all()

    return WebhookList(
        items=[
            WebhookResponse(
                id=str(w.id),
                project_id=str(w.project_id),
                url=w.url,
                enabled_events=w.enabled_events,
                is_enabled=w.is_enabled,
                created_at=w.created_at.isoformat(),
                updated_at=w.updated_at.isoformat(),
            )
            for w in webhooks
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{project_id}/webhooks/{webhook_id}",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Get webhook",
    description="Get a specific webhook configuration.",
)
async def get_webhook(
    project: UserProject,
    webhook_id: uuid.UUID,
    db: DbSession,
) -> WebhookResponse:
    """
    Get a specific webhook configuration.

    Args:
        project: Validated project owned by current user.
        webhook_id: Webhook config UUID.
        db: Database session.

    Returns:
        Webhook configuration details.
    """
    # Get webhook
    webhook = await get_webhook_config(db, project.id, webhook_id)

    return WebhookResponse(
        id=str(webhook.id),
        project_id=str(webhook.project_id),
        url=webhook.url,
        enabled_events=webhook.enabled_events,
        is_enabled=webhook.is_enabled,
        created_at=webhook.created_at.isoformat(),
        updated_at=webhook.updated_at.isoformat(),
    )


@router.patch(
    "/{project_id}/webhooks/{webhook_id}",
    response_model=WebhookResponse | WebhookWithSecretResponse,
    status_code=status.HTTP_200_OK,
    summary="Update webhook",
    description="Update a webhook configuration. If regenerate_secret is true, "
    "a new secret will be generated and returned.",
)
async def update_webhook(
    project: UserProject,
    webhook_id: uuid.UUID,
    data: WebhookUpdate,
    db: DbSession,
) -> WebhookResponse | WebhookWithSecretResponse:
    """
    Update a webhook configuration.

    Args:
        project: Validated project owned by current user.
        webhook_id: Webhook config UUID.
        data: Fields to update.
        db: Database session.

    Returns:
        Updated webhook configuration (with secret if regenerated).
    """
    # Get webhook
    webhook = await get_webhook_config(db, project.id, webhook_id)

    # Validate new event types if provided
    if data.enabled_events is not None:
        validate_events(data.enabled_events)
        webhook.enabled_events = data.enabled_events

    # Update fields
    if data.url is not None:
        webhook.url = str(data.url)

    if data.is_enabled is not None:
        webhook.is_enabled = data.is_enabled

    # Regenerate secret if requested
    new_secret: str | None = None
    if data.regenerate_secret:
        new_secret = generate_secure_token(32)
        webhook.secret = encrypt_token(new_secret)

    await db.commit()
    await db.refresh(webhook)

    # Return with secret if regenerated
    if new_secret:
        return WebhookWithSecretResponse(
            id=str(webhook.id),
            project_id=str(webhook.project_id),
            url=webhook.url,
            secret=new_secret,
            enabled_events=webhook.enabled_events,
            is_enabled=webhook.is_enabled,
            created_at=webhook.created_at.isoformat(),
            updated_at=webhook.updated_at.isoformat(),
        )

    return WebhookResponse(
        id=str(webhook.id),
        project_id=str(webhook.project_id),
        url=webhook.url,
        enabled_events=webhook.enabled_events,
        is_enabled=webhook.is_enabled,
        created_at=webhook.created_at.isoformat(),
        updated_at=webhook.updated_at.isoformat(),
    )


@router.delete(
    "/{project_id}/webhooks/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete webhook",
    description="Delete a webhook configuration and all its delivery history.",
)
async def delete_webhook(
    project: UserProject,
    webhook_id: uuid.UUID,
    db: DbSession,
) -> None:
    """
    Delete a webhook configuration.

    Args:
        project: Validated project owned by current user.
        webhook_id: Webhook config UUID.
        db: Database session.
    """
    # Get webhook
    webhook = await get_webhook_config(db, project.id, webhook_id)

    # Delete (cascades to deliveries)
    await db.delete(webhook)
    await db.commit()


@router.get(
    "/{project_id}/webhooks/{webhook_id}/deliveries",
    response_model=WebhookDeliveryList,
    status_code=status.HTTP_200_OK,
    summary="List deliveries",
    description="List delivery history for a webhook with optional status filter.",
)
async def list_deliveries(
    project: UserProject,
    webhook_id: uuid.UUID,
    db: DbSession,
    pagination: Pagination,
    delivery_status: str | None = Query(
        None,
        alias="status",
        description="Filter by status: pending, success, failed",
    ),
) -> WebhookDeliveryList:
    """
    List delivery history for a webhook.

    Args:
        project: Validated project owned by current user.
        webhook_id: Webhook config UUID.
        db: Database session.
        pagination: Pagination parameters.
        delivery_status: Optional status filter.

    Returns:
        Paginated list of delivery records.
    """
    # Verify webhook exists
    await get_webhook_config(db, project.id, webhook_id)

    # Build query
    query = select(WebhookDelivery).where(WebhookDelivery.webhook_config_id == webhook_id)

    if delivery_status is not None:
        # Validate status
        valid_statuses = [s.value for s in DeliveryStatus]
        if delivery_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )
        query = query.where(WebhookDelivery.delivery_status == delivery_status)

    # Get total count
    count_query = select(func.count(WebhookDelivery.id)).where(
        WebhookDelivery.webhook_config_id == webhook_id
    )
    if delivery_status is not None:
        count_query = count_query.where(WebhookDelivery.delivery_status == delivery_status)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get paginated deliveries
    query = query.order_by(WebhookDelivery.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.limit)

    result = await db.execute(query)
    deliveries = result.scalars().all()

    return WebhookDeliveryList(
        items=[
            WebhookDeliveryResponse(
                id=str(d.id),
                webhook_config_id=str(d.webhook_config_id),
                event_type=d.event_type,
                delivery_status=d.delivery_status,
                attempts=d.attempts,
                last_attempt_at=d.last_attempt_at.isoformat() if d.last_attempt_at else None,
                response_status=d.response_status,
                response_body=d.response_body,
                next_retry_at=d.next_retry_at.isoformat() if d.next_retry_at else None,
                created_at=d.created_at.isoformat(),
            )
            for d in deliveries
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "/{project_id}/webhooks/{webhook_id}/test",
    response_model=WebhookTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Test webhook",
    description="Send a test event to the webhook endpoint.",
)
async def test_webhook(
    project: UserProject,
    webhook_id: uuid.UUID,
    data: WebhookTestRequest,
    db: DbSession,
) -> WebhookTestResponse:
    """
    Send a test event to a webhook.

    Creates a delivery record and attempts immediate delivery.

    Args:
        project: Validated project owned by current user.
        webhook_id: Webhook config UUID.
        data: Test request data.
        db: Database session.

    Returns:
        Test result with delivery ID.
    """
    from datetime import UTC

    # Get webhook
    webhook = await get_webhook_config(db, project.id, webhook_id)

    if not webhook.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot test a disabled webhook. Enable it first.",
        )

    # Create test event payload
    now = datetime.now(UTC)
    test_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": data.event_type,
        "occurred_at": now.isoformat(),
        "project_id": str(project.id),
        "delivery_id": str(uuid.uuid4()),
        "payload": {
            "message": "This is a test webhook delivery",
            "timestamp": now.isoformat(),
        },
    }

    # Create delivery record
    delivery = WebhookDelivery(
        webhook_config_id=webhook.id,
        event_type=data.event_type,
        payload=test_payload,
        delivery_status=DeliveryStatus.PENDING.value,
    )

    db.add(delivery)
    await db.commit()
    await db.refresh(delivery)

    # Note: Actual delivery will be handled by the delivery service
    # For now, we just create the pending delivery record

    return WebhookTestResponse(
        delivery_id=str(delivery.id),
        status="pending",
        message="Test event queued for delivery. Check delivery history for results.",
    )
