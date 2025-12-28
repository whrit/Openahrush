"""
Health check endpoints.

Provides endpoints for:
- Basic liveness check (/healthz)
- Detailed readiness check (/readyz) with dependency status
"""

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from semrush_api.deps import DbSession
from semrush_core import get_settings

router = APIRouter()


class HealthzResponse(BaseModel):
    """Response model for liveness check."""

    ok: bool = Field(..., description="Whether the service is alive")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Response timestamp")


class DependencyCheck(BaseModel):
    """Status of a single dependency check."""

    status: str = Field(..., description="Check status (ok/error)")
    latency_ms: float | None = Field(None, description="Response latency in milliseconds")
    error: str | None = Field(None, description="Error message if check failed")


class ReadyzResponse(BaseModel):
    """Response model for readiness check."""

    ok: bool = Field(..., description="Whether all checks passed")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Response timestamp")
    environment: str = Field(..., description="Deployment environment")
    checks: dict[str, DependencyCheck] = Field(..., description="Individual dependency checks")


# Keep legacy models for backward compatibility
class HealthStatus(BaseModel):
    """Basic health check response (legacy)."""

    status: str = Field(..., description="Health status (healthy/unhealthy)")
    timestamp: datetime = Field(..., description="Response timestamp")
    version: str = Field(..., description="API version")


class DependencyStatus(BaseModel):
    """Status of a single dependency (legacy)."""

    name: str = Field(..., description="Dependency name")
    status: str = Field(..., description="Status (ok/error)")
    latency_ms: float | None = Field(None, description="Response latency in milliseconds")
    message: str | None = Field(None, description="Error message if unhealthy")


class ReadinessStatus(BaseModel):
    """Detailed readiness check response (legacy)."""

    status: str = Field(..., description="Overall status (ready/not_ready)")
    timestamp: datetime = Field(..., description="Response timestamp")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Deployment environment")
    dependencies: list[DependencyStatus] = Field(..., description="Dependency statuses")


@router.get(
    "/healthz",
    response_model=HealthzResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Basic health check to verify the API is running. Use for Kubernetes liveness probes.",
)
async def healthz() -> HealthzResponse:
    """
    Basic liveness check.

    Returns a simple healthy status if the API is running.
    Does not check dependencies - use /readyz for that.
    """
    return HealthzResponse(
        ok=True,
        version="0.1.0",
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/readyz",
    response_model=ReadyzResponse,
    summary="Readiness check",
    description="Detailed readiness check including all dependencies. Use for Kubernetes readiness probes.",
    responses={
        200: {"description": "Service is ready"},
        503: {
            "description": "Service not ready",
            "content": {
                "application/json": {
                    "example": {
                        "ok": False,
                        "version": "0.1.0",
                        "timestamp": "2024-01-15T12:00:00Z",
                        "environment": "production",
                        "checks": {
                            "database": {
                                "status": "error",
                                "error": "Connection refused",
                            }
                        },
                    }
                }
            },
        },
    },
)
async def readyz(db: DbSession, response: Response) -> ReadyzResponse:
    """
    Detailed readiness check.

    Verifies all critical dependencies are available:
    - Database connection

    Returns 503 if any critical dependency is unavailable.
    """
    settings = get_settings()
    checks: dict[str, DependencyCheck] = {}
    all_healthy = True

    # Check database
    db_check = await _check_database(db)
    checks["database"] = db_check
    if db_check.status != "ok":
        all_healthy = False

    # Set appropriate status code
    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyzResponse(
        ok=all_healthy,
        version="0.1.0",
        timestamp=datetime.now(timezone.utc),
        environment=settings.environment,
        checks=checks,
    )


async def _check_database(db: DbSession) -> DependencyCheck:
    """
    Check database connectivity.

    Executes a simple query to verify the database is accessible.
    """
    start = time.perf_counter()

    try:
        await db.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000

        return DependencyCheck(
            status="ok",
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000

        return DependencyCheck(
            status="error",
            latency_ms=round(latency, 2),
            error=str(e),
        )


# Legacy endpoints for backward compatibility


@router.get(
    "/health",
    response_model=HealthStatus,
    status_code=status.HTTP_200_OK,
    summary="Liveness check (legacy)",
    description="Legacy health check endpoint. Use /healthz instead.",
    deprecated=True,
)
async def health_check() -> HealthStatus:
    """
    Basic liveness check (legacy).

    Deprecated: Use /healthz instead.
    """
    return HealthStatus(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        version="0.1.0",
    )


@router.get(
    "/ready",
    response_model=ReadinessStatus,
    status_code=status.HTTP_200_OK,
    summary="Readiness check (legacy)",
    description="Legacy readiness check endpoint. Use /readyz instead.",
    deprecated=True,
    responses={
        503: {
            "description": "Service not ready",
            "content": {
                "application/json": {
                    "example": {
                        "status": "not_ready",
                        "timestamp": "2024-01-15T12:00:00Z",
                        "version": "0.1.0",
                        "environment": "production",
                        "dependencies": [
                            {"name": "database", "status": "error", "message": "Connection refused"}
                        ],
                    }
                }
            },
        }
    },
)
async def readiness_check(db: DbSession) -> ReadinessStatus:
    """
    Detailed readiness check (legacy).

    Deprecated: Use /readyz instead.
    """
    settings = get_settings()
    dependencies: list[DependencyStatus] = []
    all_healthy = True

    # Check database
    db_status = await _check_database_legacy(db)
    dependencies.append(db_status)
    if db_status.status != "ok":
        all_healthy = False

    return ReadinessStatus(
        status="ready" if all_healthy else "not_ready",
        timestamp=datetime.now(timezone.utc),
        version="0.1.0",
        environment=settings.environment,
        dependencies=dependencies,
    )


async def _check_database_legacy(db: DbSession) -> DependencyStatus:
    """Check database connectivity (legacy format)."""
    start = time.perf_counter()

    try:
        await db.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000

        return DependencyStatus(
            name="database",
            status="ok",
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000

        return DependencyStatus(
            name="database",
            status="error",
            latency_ms=round(latency, 2),
            message=str(e),
        )
