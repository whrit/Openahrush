"""
FastAPI application entry point.

Configures the FastAPI application with:
- Lifespan management for startup/shutdown
- CORS middleware
- Exception handlers
- Router registration
- OpenAPI documentation
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from semrush_core import get_settings
from semrush_core.database import dispose_engine, get_engine
from semrush_core.security.jwt import TokenError

from semrush_api.routers import (
    alerts,
    auth,
    backlinks,
    commoncrawl,
    diffs,
    exports,
    health,
    integrations,
    issues,
    projects,
    settings,
    webhooks,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifespan events.

    Startup:
    - Initialize database connection pool
    - Validate configuration
    - Log startup info

    Shutdown:
    - Close database connections
    - Clean up resources
    """
    settings = get_settings()
    logger.info(
        "Starting %s in %s mode",
        settings.app_name,
        settings.environment,
    )

    # Initialize database engine (validates connection)
    try:
        _ = get_engine()
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)
        raise

    yield

    # Shutdown
    logger.info("Shutting down %s", settings.app_name)
    await dispose_engine()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Open-source, self-hostable SEO platform providing site audits, "
            "search console integrations, and backlink analysis."
        ),
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else "/api/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Total-Count"],
    )

    # Register exception handlers
    register_exception_handlers(app)

    # Register routers
    register_routers(app)

    return app


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers."""

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: ValidationError,
    ) -> JSONResponse:
        """Handle Pydantic validation errors."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "validation_error",
                "message": "Request validation failed",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(TokenError)
    async def token_exception_handler(
        request: Request,
        exc: TokenError,
    ) -> JSONResponse:
        """Handle JWT token errors."""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "authentication_error",
                "message": str(exc),
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        """Handle HTTP exceptions with consistent format."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": _status_to_error_code(exc.status_code),
                "message": exc.detail,
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        settings = get_settings()
        logger.exception("Unhandled exception: %s", exc)

        # Only show details in debug mode
        message = str(exc) if settings.debug else "An unexpected error occurred"

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": message,
            },
        )


def _status_to_error_code(status_code: int) -> str:
    """Convert HTTP status code to error code string."""
    error_codes: dict[int, str] = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        500: "internal_error",
        502: "bad_gateway",
        503: "service_unavailable",
    }
    return error_codes.get(status_code, "error")


def register_routers(app: FastAPI) -> None:
    """Register API routers."""
    # Health check (no prefix, no auth)
    app.include_router(health.router, tags=["Health"])

    # Authentication (no prefix - /auth/login, /auth/logout, /me)
    app.include_router(auth.router, tags=["Authentication"])

    # Projects CRUD (no prefix - /projects)
    app.include_router(projects.router, tags=["Projects"])

    # Project settings (no prefix - /projects/{id}/settings)
    app.include_router(settings.router, tags=["Settings"])

    # Integrations (no prefix - /integrations)
    app.include_router(integrations.router, tags=["Integrations"])

    # Issues (no prefix - /crawls/{id}/issues, /projects/{id}/issues)
    app.include_router(issues.router, tags=["Issues"])

    # Diffs (no prefix - /projects/{id}/issues/diffs)
    app.include_router(diffs.router, tags=["Diffs"])

    # Alerts (no prefix - /projects/{id}/alerts)
    app.include_router(alerts.router, tags=["Alerts"])

    # Backlinks - Domain Explorer (/links/domain/...)
    app.include_router(backlinks.links_router, tags=["Backlinks"])

    # Backlinks - Project Backlinks (/projects/{id}/backlinks/...)
    app.include_router(backlinks.projects_router, tags=["Project Backlinks"])

    # Common Crawl (/commoncrawl/...)
    app.include_router(commoncrawl.router, tags=["Common Crawl"])

    # Webhooks (/projects/{id}/webhooks/...)
    app.include_router(webhooks.router, tags=["Webhooks"])

    # Exports (/projects/{id}/exports/...)
    app.include_router(exports.router, tags=["Exports"])


# Create the application instance
app = create_app()


def run() -> None:
    """Run the API server using uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "semrush_api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    run()
