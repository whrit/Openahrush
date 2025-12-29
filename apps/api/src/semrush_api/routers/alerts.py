"""
Alerts API endpoints.

Provides endpoints for:
- GET /projects/{project_id}/alerts - List alerts with filters
- POST /projects/{project_id}/alerts/rules - Create/update alert rules
- GET /projects/{project_id}/alerts/rules - List alert rules
- PATCH /projects/{project_id}/alerts/{alert_id}/acknowledge - Acknowledge alert
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from semrush_core.models import Alert, AlertRule
from sqlalchemy import func, select

from semrush_api.deps import DbSession, Pagination, UserProject

router = APIRouter(prefix="/projects", tags=["Alerts"])


class AlertRuleConfig(BaseModel):
    """Configuration for an alert rule."""

    threshold: float = Field(default=30.0, description="Threshold percentage for triggering")
    min_impressions: int = Field(default=100, description="Minimum impressions for CTR checks")


class AlertRuleCreate(BaseModel):
    """Request body for creating an alert rule."""

    rule_type: str = Field(
        ..., description="Type of rule: visibility_drop, ctr_opportunity, regression"
    )
    config: AlertRuleConfig = Field(default_factory=AlertRuleConfig)
    is_enabled: bool = Field(default=True)


class AlertRuleResponse(BaseModel):
    """Response for an alert rule."""

    id: str
    project_id: str
    rule_type: str
    config: dict[str, Any]
    is_enabled: bool
    created_at: str

    model_config = {"from_attributes": True}


class AlertRuleList(BaseModel):
    """Response for list of alert rules."""

    items: list[AlertRuleResponse]


class AlertResponse(BaseModel):
    """Response for an alert."""

    id: str
    project_id: str
    alert_rule_id: str | None
    kind: str
    entity_type: str
    entity_key: str
    severity: str
    payload: dict[str, Any]
    is_acknowledged: bool
    created_at: str

    model_config = {"from_attributes": True}


class AlertList(BaseModel):
    """Response for list of alerts."""

    items: list[AlertResponse]
    total: int
    page: int
    page_size: int


@router.get(
    "/{project_id}/alerts",
    response_model=AlertList,
    status_code=status.HTTP_200_OK,
    summary="List alerts",
    description="List alerts for a project with optional filters.",
)
async def list_alerts(
    db: DbSession,
    project: UserProject,
    pagination: Pagination,
    severity: str | None = Query(None, description="Filter by severity: info, warn, critical"),
    kind: str | None = Query(
        None, description="Filter by kind: visibility_drop, ctr_opportunity, regression"
    ),
    is_acknowledged: bool | None = Query(None, description="Filter by acknowledgement status"),
) -> AlertList:
    """
    List alerts for a project.

    Args:
        db: Database session.
        project: Project retrieved via dependency (validates ownership).
        pagination: Pagination parameters.
        severity: Optional severity filter.
        kind: Optional kind filter.
        is_acknowledged: Optional acknowledgement status filter.

    Returns:
        Paginated list of alerts.
    """
    # Build query
    query = select(Alert).where(Alert.project_id == project.id)

    if severity is not None:
        query = query.where(Alert.severity == severity)
    if kind is not None:
        query = query.where(Alert.kind == kind)
    if is_acknowledged is not None:
        query = query.where(Alert.is_acknowledged == is_acknowledged)

    # Get total count
    count_result = await db.execute(
        select(func.count(Alert.id)).where(Alert.project_id == project.id)
    )
    total = count_result.scalar() or 0

    # Get paginated alerts
    query = query.order_by(Alert.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.limit)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return AlertList(
        items=[
            AlertResponse(
                id=str(a.id),
                project_id=str(a.project_id),
                alert_rule_id=str(a.alert_rule_id) if a.alert_rule_id else None,
                kind=a.kind,
                entity_type=a.entity_type,
                entity_key=a.entity_key,
                severity=a.severity,
                payload=a.payload,
                is_acknowledged=a.is_acknowledged,
                created_at=a.created_at.isoformat(),
            )
            for a in alerts
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "/{project_id}/alerts/rules",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create alert rule",
    description="Create a new alert rule for a project.",
)
async def create_alert_rule(
    data: AlertRuleCreate,
    db: DbSession,
    project: UserProject,
) -> AlertRuleResponse:
    """
    Create a new alert rule.

    Args:
        data: Alert rule creation data.
        db: Database session.
        project: Project retrieved via dependency (validates ownership).

    Returns:
        Created alert rule.
    """
    # Validate rule type
    valid_types = ["visibility_drop", "ctr_opportunity", "regression"]
    if data.rule_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid rule type. Must be one of: {', '.join(valid_types)}",
        )

    # Create rule
    rule = AlertRule(
        project_id=project.id,
        rule_type=data.rule_type,
        config=data.config.model_dump(),
        is_enabled=data.is_enabled,
    )

    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return AlertRuleResponse(
        id=str(rule.id),
        project_id=str(rule.project_id),
        rule_type=rule.rule_type,
        config=rule.config,
        is_enabled=rule.is_enabled,
        created_at=rule.created_at.isoformat(),
    )


@router.get(
    "/{project_id}/alerts/rules",
    response_model=AlertRuleList,
    status_code=status.HTTP_200_OK,
    summary="List alert rules",
    description="List all alert rules for a project.",
)
async def list_alert_rules(
    db: DbSession,
    project: UserProject,
) -> AlertRuleList:
    """
    List alert rules for a project.

    Args:
        db: Database session.
        project: Project retrieved via dependency (validates ownership).

    Returns:
        List of alert rules.
    """
    result = await db.execute(
        select(AlertRule).where(AlertRule.project_id == project.id).order_by(AlertRule.created_at)
    )
    rules = result.scalars().all()

    return AlertRuleList(
        items=[
            AlertRuleResponse(
                id=str(r.id),
                project_id=str(r.project_id),
                rule_type=r.rule_type,
                config=r.config,
                is_enabled=r.is_enabled,
                created_at=r.created_at.isoformat(),
            )
            for r in rules
        ]
    )


@router.patch(
    "/{project_id}/alerts/{alert_id}/acknowledge",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Acknowledge alert",
    description="Mark an alert as acknowledged.",
)
async def acknowledge_alert(
    alert_id: UUID,
    db: DbSession,
    project: UserProject,
) -> None:
    """
    Acknowledge an alert.

    Args:
        alert_id: Alert UUID.
        db: Database session.
        project: Project retrieved via dependency (validates ownership).

    Raises:
        HTTPException: 404 if alert not found.
    """
    # Get alert
    result = await db.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.project_id == project.id,
        )
    )
    alert = result.scalar_one_or_none()

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    alert.is_acknowledged = True
    await db.commit()
