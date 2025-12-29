"""
Integration endpoints for OAuth-connected third-party services.

Provides endpoints for:
- POST /integrations/{provider}/connect - Start OAuth flow
- POST /integrations/{provider}/callback - Handle OAuth callback
- DELETE /integrations/{provider}/disconnect - Revoke tokens
- GET /integrations - List connected integrations
- GET /integrations/{provider}/status - Get connection status
- GET /integrations/{provider}/health - Get integration health
- GET /projects/{project_id}/sync-status - Get sync status for project
- GET /projects/{project_id}/data-freshness - Get data freshness for project
- POST /projects/{project_id}/mappings/{mapping_id}/sync - Trigger manual sync
"""

import asyncio
import logging
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, status
from semrush_core import get_settings
from semrush_core.models import IntegrationMapping, SyncRun
from semrush_core.models.integration_account import IntegrationAccount
from semrush_core.models.sync_run import SyncStatus as SyncRunStatus
from semrush_core.oauth.state import AsyncOAuthStateManager
from semrush_core.security.encryption import DecryptionError, decrypt_token
from semrush_integrations.oauth.google import GoogleOAuthProvider
from semrush_integrations.oauth.microsoft import MicrosoftOAuthProvider
from semrush_integrations.services.health_service import IntegrationHealthService
from semrush_integrations.services.property_service import PropertyMappingService, PropertyService
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from semrush_api.deps import CurrentUser, DbSession, UserProject
from semrush_api.schemas.integration import (
    IntegrationCallbackRequest,
    IntegrationCallbackResponse,
    IntegrationConnectResponse,
    IntegrationDisconnectResponse,
    IntegrationListResponse,
    IntegrationPropertyResponse,
    IntegrationProvider,
    IntegrationStatus,
    MappingCreateRequest,
    MappingListResponse,
    MappingResponse,
    PropertyListResponse,
    PropertySyncResponse,
)
from semrush_api.schemas.sync import (
    DataFreshnessResponse,
    IntegrationHealthResponse,
    ProjectDataFreshnessResponse,
    ProjectSyncStatusResponse,
    SyncStatusResponse,
    TriggerSyncRequest,
    TriggerSyncResponse,
)

router = APIRouter()


# =============================================================================
# Redis-based OAuth State Management (FIX Issue 1)
# =============================================================================

logger = logging.getLogger(__name__)

# Module-level state manager singleton (with Redis or in-memory fallback)
_oauth_state_manager: AsyncOAuthStateManager | None = None


def _try_get_redis_client() -> aioredis.Redis | None:  # type: ignore[type-arg]
    """
    Try to get an async Redis client for OAuth state storage.

    Returns None if Redis is not configured or unavailable.

    Returns:
        Async Redis client instance or None.
    """
    try:
        settings = get_settings()
        return aioredis.from_url(settings.redis_url, decode_responses=True)
    except Exception as e:
        logger.warning(f"Redis client creation failed, using in-memory fallback: {e}")
        return None


def get_oauth_state_manager() -> AsyncOAuthStateManager:
    """
    Get the OAuth state manager with Redis backend (or in-memory fallback).

    Uses Redis as the primary storage for production (multi-instance safe).
    Falls back to in-memory storage when Redis is unavailable (for testing).

    Returns:
        AsyncOAuthStateManager configured with 10-minute TTL.
    """
    global _oauth_state_manager

    if _oauth_state_manager is None:
        redis_client = _try_get_redis_client()
        _oauth_state_manager = AsyncOAuthStateManager(redis_client, ttl_seconds=600)

    return _oauth_state_manager


def reset_oauth_state_manager() -> None:
    """
    Reset the OAuth state manager singleton.

    Used for testing to ensure a fresh state between tests.
    """
    global _oauth_state_manager
    _oauth_state_manager = None


# =============================================================================
# Singleton Sync Engine (FIX Issue 4)
# =============================================================================

# Module-level sync engine singleton to avoid connection pool exhaustion
_sync_engine: Any = None
_sync_session_factory: sessionmaker[Session] | None = None


def _get_sync_engine() -> Any:
    """
    Get or create a singleton sync engine for synchronous database operations.

    This prevents connection pool exhaustion by reusing a single engine
    instead of creating a new one per request.

    Returns:
        SQLAlchemy sync Engine instance.
    """
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        # Convert async URL to sync URL
        sync_url = settings.database_url.replace("+asyncpg", "").replace("+psycopg", "")
        _sync_engine = create_engine(
            sync_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _sync_engine


def _get_sync_session_factory() -> sessionmaker[Session]:
    """
    Get or create a singleton session factory for sync sessions.

    Returns:
        SQLAlchemy sessionmaker instance.
    """
    global _sync_session_factory
    if _sync_session_factory is None:
        engine = _get_sync_engine()
        _sync_session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _sync_session_factory


def get_sync_session() -> Session:
    """
    Get a synchronous session for services that require sync operations.

    Uses a module-level singleton engine to prevent connection pool exhaustion.

    Returns:
        Synchronous SQLAlchemy Session.
    """
    factory = _get_sync_session_factory()
    return factory()


# =============================================================================
# Provider Configuration
# =============================================================================

VALID_PROVIDERS = {
    IntegrationProvider.GOOGLE_SEARCH_CONSOLE.value,
    IntegrationProvider.GOOGLE_ANALYTICS.value,
    IntegrationProvider.BING_WEBMASTER_TOOLS.value,
}

# Map providers to their OAuth provider classes
PROVIDER_MAP = {
    IntegrationProvider.GOOGLE_SEARCH_CONSOLE.value: "google",
    IntegrationProvider.GOOGLE_ANALYTICS.value: "google",
    IntegrationProvider.BING_WEBMASTER_TOOLS.value: "microsoft",
}


def validate_provider(provider: str) -> None:
    """
    Validate that the provider is supported.

    Args:
        provider: Provider name to validate.

    Raises:
        HTTPException: 400 if provider is not supported.
    """
    if provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider: {provider}. Valid providers are: {', '.join(VALID_PROVIDERS)}",
        )


def get_oauth_provider(provider: str) -> GoogleOAuthProvider | MicrosoftOAuthProvider:
    """
    Get the OAuth provider instance for a given provider.

    Args:
        provider: Provider name.

    Returns:
        Configured OAuth provider instance.
    """
    settings = get_settings()
    provider_type = PROVIDER_MAP[provider]

    if provider_type == "google":
        client_secret = ""
        if settings.google_client_secret is not None:
            client_secret = settings.google_client_secret.get_secret_value()
        return GoogleOAuthProvider(
            client_id=settings.google_client_id or "",
            client_secret=client_secret,
            redirect_uri=settings.google_redirect_uri or "",
        )
    else:  # microsoft
        client_secret = ""
        if settings.microsoft_client_secret is not None:
            client_secret = settings.microsoft_client_secret.get_secret_value()
        return MicrosoftOAuthProvider(
            client_id=settings.microsoft_client_id or "",
            client_secret=client_secret,
            redirect_uri=settings.microsoft_redirect_uri or "",
        )


# =============================================================================
# Connect Endpoint
# =============================================================================


@router.post(
    "/integrations/{provider}/connect",
    response_model=IntegrationConnectResponse,
    status_code=status.HTTP_200_OK,
    summary="Start OAuth connection flow",
    description="Initiate OAuth flow for connecting an integration. Returns authorization URL for user redirect.",
    responses={
        400: {
            "description": "Invalid provider",
            "content": {
                "application/json": {
                    "example": {
                        "error": "bad_request",
                        "message": "Invalid provider: invalid_provider",
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
        },
        409: {
            "description": "Integration already connected",
            "content": {
                "application/json": {
                    "example": {
                        "error": "conflict",
                        "message": "Integration google_search_console is already connected",
                    }
                }
            },
        },
    },
)
async def connect_integration(
    provider: str,
    current_user: CurrentUser,
    db: DbSession,
) -> IntegrationConnectResponse:
    """
    Start OAuth connection flow for an integration.

    Generates an authorization URL that the client should redirect the user to.
    The state token must be preserved and passed back in the callback.

    Args:
        provider: Integration provider to connect.
        current_user: Current authenticated user.
        db: Database session.

    Returns:
        IntegrationConnectResponse with authorization URL and state token.

    Raises:
        HTTPException: 400 if invalid provider, 409 if already connected.
    """
    validate_provider(provider)

    # Check if already connected
    result = await db.execute(
        select(IntegrationAccount).where(
            IntegrationAccount.user_id == current_user.user_id,
            IntegrationAccount.provider == provider,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integration {provider} is already connected",
        )

    # Generate state token using Redis-backed state manager
    state_manager = get_oauth_state_manager()
    state = await state_manager.generate(str(current_user.user_id), provider)

    # Get OAuth provider and generate authorization URL
    oauth_provider = get_oauth_provider(provider)
    authorization_url = oauth_provider.get_authorization_url(state)

    return IntegrationConnectResponse(
        authorization_url=authorization_url,
        state=state,
        provider=provider,
    )


# =============================================================================
# Callback Endpoint
# =============================================================================


@router.post(
    "/integrations/{provider}/callback",
    response_model=IntegrationCallbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Handle OAuth callback",
    description="Exchange OAuth authorization code for tokens and complete integration setup.",
    responses={
        400: {
            "description": "Invalid provider or state token",
            "content": {
                "application/json": {
                    "example": {
                        "error": "bad_request",
                        "message": "Invalid or expired state token",
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
        },
        422: {
            "description": "Validation error (missing code or state)",
        },
    },
)
async def oauth_callback(
    provider: str,
    callback_data: IntegrationCallbackRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> IntegrationCallbackResponse:
    """
    Handle OAuth callback and complete integration setup.

    Validates the state token, exchanges the authorization code for tokens,
    retrieves user info from the provider, and creates the integration account.

    Args:
        provider: Integration provider.
        callback_data: OAuth callback data with code and state.
        current_user: Current authenticated user.
        db: Database session.

    Returns:
        IntegrationCallbackResponse with connection status.

    Raises:
        HTTPException: 400 if invalid provider or state, 422 if missing fields.
    """
    validate_provider(provider)

    # Validate and consume state token using Redis-backed state manager
    state_manager = get_oauth_state_manager()
    state_data = await state_manager.validate(callback_data.state)

    if state_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state token",
        )

    # Verify the state matches the current user and provider
    if state_data.get("user_id") != str(current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token does not match current user",
        )

    if state_data.get("provider") != provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token does not match provider",
        )

    # Get OAuth provider
    oauth_provider = get_oauth_provider(provider)

    # Exchange code for tokens
    try:
        tokens = await oauth_provider.exchange_code(callback_data.code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange authorization code: {e!s}",
        ) from e

    # Get user info from provider
    try:
        user_info = await oauth_provider.get_user_info(tokens.access_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to retrieve user information: {e!s}",
        ) from e

    # Create integration account
    integration_account = IntegrationAccount(
        user_id=current_user.user_id,
        provider=provider,
        provider_account_id=user_info.external_id,
        token_expires_at=tokens.expires_at,
        scopes=tokens.scopes,
        sync_status="pending",
    )

    db.add(integration_account)
    await db.commit()
    await db.refresh(integration_account)

    return IntegrationCallbackResponse(
        provider=provider,
        connected=True,
        provider_account_id=user_info.external_id,
        message="Successfully connected",
    )


# =============================================================================
# Disconnect Endpoint (FIX Issue 3)
# =============================================================================


@router.delete(
    "/integrations/{provider}/disconnect",
    response_model=IntegrationDisconnectResponse,
    status_code=status.HTTP_200_OK,
    summary="Disconnect integration",
    description="Revoke OAuth tokens and remove the integration connection.",
    responses={
        400: {
            "description": "Invalid provider",
        },
        401: {
            "description": "Not authenticated",
        },
        404: {
            "description": "Integration not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "not_found",
                        "message": "Integration google_search_console is not connected",
                    }
                }
            },
        },
    },
)
async def disconnect_integration(
    provider: str,
    current_user: CurrentUser,
    db: DbSession,
) -> IntegrationDisconnectResponse:
    """
    Disconnect an integration.

    Revokes OAuth tokens with the provider and removes the integration account
    from the database.

    Args:
        provider: Integration provider to disconnect.
        current_user: Current authenticated user.
        db: Database session.

    Returns:
        IntegrationDisconnectResponse with success message.

    Raises:
        HTTPException: 400 if invalid provider, 404 if not connected.
    """
    validate_provider(provider)

    # Find the integration account
    result = await db.execute(
        select(IntegrationAccount).where(
            IntegrationAccount.user_id == current_user.user_id,
            IntegrationAccount.provider == provider,
        )
    )
    integration_account = result.scalar_one_or_none()

    if not integration_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration {provider} is not connected",
        )

    # Attempt to revoke token with provider (best effort)
    try:
        oauth_provider = get_oauth_provider(provider)

        # Get the actual access token from the token relationship
        access_token = None
        if integration_account.token and integration_account.token.access_token_encrypted:
            try:
                # Decrypt the stored token
                encrypted_token = integration_account.token.access_token_encrypted
                if isinstance(encrypted_token, bytes):
                    access_token = decrypt_token(encrypted_token).decode("utf-8")
                else:
                    access_token = decrypt_token(encrypted_token)
            except DecryptionError:
                # If decryption fails, log and continue - token might be corrupted
                pass

        # Only attempt revocation if we have a valid token
        if access_token:
            await oauth_provider.revoke_token(access_token)
    except Exception:
        # Log but don't fail - token revocation is best effort
        # The provider may have already invalidated the token
        pass

    # Delete the integration account
    await db.delete(integration_account)
    await db.commit()

    return IntegrationDisconnectResponse(
        provider=provider,
        message=f"Successfully disconnected {provider}",
    )


# =============================================================================
# List Integrations Endpoint
# =============================================================================


@router.get(
    "/integrations",
    response_model=IntegrationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List connected integrations",
    description="Get a list of all connected integrations for the current user.",
    responses={
        401: {
            "description": "Not authenticated",
        },
    },
)
async def list_integrations(
    current_user: CurrentUser,
    db: DbSession,
) -> IntegrationListResponse:
    """
    List all connected integrations.

    Returns all integration accounts for the current user with their status.

    Args:
        current_user: Current authenticated user.
        db: Database session.

    Returns:
        IntegrationListResponse with list of connected integrations.
    """
    result = await db.execute(
        select(IntegrationAccount).where(IntegrationAccount.user_id == current_user.user_id)
    )
    accounts = result.scalars().all()

    integrations = [
        IntegrationStatus(
            provider=account.provider,
            connected=True,
            provider_account_id=account.provider_account_id,
            connected_at=account.created_at,
            last_sync_at=account.last_sync_at,
            sync_status=account.sync_status,
            sync_error=account.sync_error,
        )
        for account in accounts
    ]

    return IntegrationListResponse(integrations=integrations)


# =============================================================================
# Status Endpoint
# =============================================================================


@router.get(
    "/integrations/{provider}/status",
    response_model=IntegrationStatus,
    status_code=status.HTTP_200_OK,
    summary="Get integration status",
    description="Get the connection status for a specific integration provider.",
    responses={
        400: {
            "description": "Invalid provider",
        },
        401: {
            "description": "Not authenticated",
        },
    },
)
async def get_integration_status(
    provider: str,
    current_user: CurrentUser,
    db: DbSession,
) -> IntegrationStatus:
    """
    Get status for a specific integration.

    Returns connection status and sync information for the specified provider.

    Args:
        provider: Integration provider to check.
        current_user: Current authenticated user.
        db: Database session.

    Returns:
        IntegrationStatus with connection and sync information.

    Raises:
        HTTPException: 400 if invalid provider.
    """
    validate_provider(provider)

    result = await db.execute(
        select(IntegrationAccount).where(
            IntegrationAccount.user_id == current_user.user_id,
            IntegrationAccount.provider == provider,
        )
    )
    integration_account = result.scalar_one_or_none()

    if not integration_account:
        return IntegrationStatus(
            provider=provider,
            connected=False,
            provider_account_id=None,
            connected_at=None,
            last_sync_at=None,
            sync_status=None,
            sync_error=None,
        )

    return IntegrationStatus(
        provider=integration_account.provider,
        connected=True,
        provider_account_id=integration_account.provider_account_id,
        connected_at=integration_account.created_at,
        last_sync_at=integration_account.last_sync_at,
        sync_status=integration_account.sync_status,
        sync_error=integration_account.sync_error,
    )


# =============================================================================
# Health Endpoint
# =============================================================================


@router.get(
    "/integrations/{provider}/health",
    response_model=IntegrationHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Get integration health",
    description="Get overall health status for a specific integration provider.",
    responses={
        400: {
            "description": "Invalid provider",
        },
        401: {
            "description": "Not authenticated",
        },
    },
)
async def get_integration_health(
    provider: str,
    current_user: CurrentUser,
    db: DbSession,
) -> IntegrationHealthResponse:
    """
    Get health status for a specific integration.

    Returns overall health including token validity, property count, and sync status.

    Args:
        provider: Integration provider to check.
        current_user: Current authenticated user.
        db: Database session.

    Returns:
        IntegrationHealthResponse with health information.

    Raises:
        HTTPException: 400 if invalid provider.
    """
    validate_provider(provider)

    # Get integration account
    result = await db.execute(
        select(IntegrationAccount).where(
            IntegrationAccount.user_id == current_user.user_id,
            IntegrationAccount.provider == provider,
        )
    )
    integration_account = result.scalar_one_or_none()

    if not integration_account:
        return IntegrationHealthResponse(
            provider=provider,
            connected=False,
            token_valid=False,
            properties_count=0,
            last_sync=None,
            is_healthy=False,
            status_message="Integration is not connected",
        )

    # Use synchronous session for health service (using singleton engine)
    sync_session = get_sync_session()
    try:
        health_service = IntegrationHealthService(sync_session)
        health_list = health_service.get_integration_health(current_user.user_id)

        # Find the health for this provider
        for health in health_list:
            if health.provider == provider:
                return IntegrationHealthResponse(
                    provider=health.provider,
                    connected=health.connected,
                    token_valid=health.token_valid,
                    properties_count=health.properties_count,
                    last_sync=health.last_sync,
                    is_healthy=health.is_healthy,
                    status_message=health.status_message,
                )

        # Fallback if not found in health list
        return IntegrationHealthResponse(
            provider=provider,
            connected=True,
            token_valid=False,
            properties_count=0,
            last_sync=None,
            is_healthy=False,
            status_message="Unable to determine health status",
        )
    finally:
        sync_session.close()


# =============================================================================
# Project Sync Status Endpoint
# =============================================================================


@router.get(
    "/projects/{project_id}/sync-status",
    response_model=ProjectSyncStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project sync status",
    description="Get sync status for all integration mappings in a project.",
    responses={
        401: {
            "description": "Not authenticated",
        },
        404: {
            "description": "Project not found",
        },
    },
)
async def get_project_sync_status(
    project: UserProject,
) -> ProjectSyncStatusResponse:
    """
    Get sync status for all mappings in a project.

    Returns sync status for each integration mapping including last sync time,
    next scheduled sync, error count, and health status.

    Args:
        project: Project retrieved via dependency (validates ownership).

    Returns:
        ProjectSyncStatusResponse with sync status for all mappings.

    Raises:
        HTTPException: 404 if project not found.
    """
    project_id = project.id

    # Use synchronous session for health service (using singleton engine)
    sync_session = get_sync_session()
    try:
        health_service = IntegrationHealthService(sync_session)
        statuses = health_service.get_project_sync_status(project_id)

        mapping_responses = [
            SyncStatusResponse(
                mapping_id=s.mapping_id,
                provider=s.provider,
                property_id=s.property_id,
                status=s.status,
                last_sync_at=s.last_sync_at,
                next_sync_at=s.next_sync_at,
                error_count=s.error_count,
                error_message=s.error_message,
                is_healthy=s.is_healthy,
                status_message=s.status_message,
            )
            for s in statuses
        ]

        overall_healthy = (
            all(s.is_healthy for s in mapping_responses) if mapping_responses else True
        )

        return ProjectSyncStatusResponse(
            project_id=project_id,
            mappings=mapping_responses,
            overall_healthy=overall_healthy,
        )
    finally:
        sync_session.close()


# =============================================================================
# Project Data Freshness Endpoint
# =============================================================================


@router.get(
    "/projects/{project_id}/data-freshness",
    response_model=ProjectDataFreshnessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project data freshness",
    description="Get data freshness metrics for all integration mappings in a project.",
    responses={
        401: {
            "description": "Not authenticated",
        },
        404: {
            "description": "Project not found",
        },
    },
)
async def get_project_data_freshness(
    project: UserProject,
) -> ProjectDataFreshnessResponse:
    """
    Get data freshness for all mappings in a project.

    Returns freshness metrics including latest data date, expected lag,
    days behind, and coverage percentage.

    Args:
        project: Project retrieved via dependency (validates ownership).

    Returns:
        ProjectDataFreshnessResponse with freshness for all mappings.

    Raises:
        HTTPException: 404 if project not found.
    """
    project_id = project.id

    # Use synchronous session for health service (using singleton engine)
    sync_session = get_sync_session()
    try:
        health_service = IntegrationHealthService(sync_session)
        freshness_list = health_service.get_project_data_freshness(project_id)

        mapping_responses = [
            DataFreshnessResponse(
                mapping_id=f.mapping_id,
                provider=f.provider,
                property_id=f.property_id,
                latest_data_date=f.latest_data_date,
                expected_lag_days=f.expected_lag_days,
                days_behind=f.days_behind,
                coverage_pct=f.coverage_pct,
                is_fresh=f.is_fresh,
                status_message=f.status_message,
            )
            for f in freshness_list
        ]

        overall_fresh = all(f.is_fresh for f in mapping_responses) if mapping_responses else True

        return ProjectDataFreshnessResponse(
            project_id=project_id,
            mappings=mapping_responses,
            overall_fresh=overall_fresh,
        )
    finally:
        sync_session.close()


# =============================================================================
# Trigger Manual Sync Endpoint
# =============================================================================


@router.post(
    "/projects/{project_id}/mappings/{mapping_id}/sync",
    response_model=TriggerSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger manual sync",
    description="Trigger a manual data sync for a specific integration mapping.",
    responses={
        401: {
            "description": "Not authenticated",
        },
        404: {
            "description": "Project or mapping not found",
        },
        409: {
            "description": "Sync already in progress",
        },
    },
)
async def trigger_manual_sync(
    mapping_id: UUID,
    sync_request: TriggerSyncRequest,
    db: DbSession,
    project: UserProject,
) -> TriggerSyncResponse:
    """
    Trigger a manual sync for an integration mapping.

    Creates a new sync run in queued state. The sync will be processed
    by the worker service.

    Args:
        mapping_id: Integration mapping UUID.
        sync_request: Sync configuration (mode, date range).
        db: Database session.
        project: Project retrieved via dependency (validates ownership).

    Returns:
        TriggerSyncResponse with sync run ID and status.

    Raises:
        HTTPException: 404 if project/mapping not found, 409 if sync in progress.
    """
    project_id = project.id

    # Find the mapping
    result = await db.execute(
        select(IntegrationMapping).where(
            IntegrationMapping.id == mapping_id,
            IntegrationMapping.project_id == project_id,
        )
    )
    mapping = result.scalar_one_or_none()

    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration mapping not found",
        )

    # Check for existing active sync
    result = await db.execute(
        select(SyncRun).where(
            SyncRun.integration_mapping_id == mapping_id,
            SyncRun.status.in_([SyncRunStatus.QUEUED.value, SyncRunStatus.RUNNING.value]),
        )
    )
    existing_sync = result.scalar_one_or_none()

    if existing_sync:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A sync is already in progress for this mapping",
        )

    # Get provider and property from mapping
    provider = mapping.integration_property.provider if mapping.integration_property else "unknown"
    property_id = mapping.integration_property.property_id if mapping.integration_property else ""

    # Create new sync run
    sync_run = SyncRun(
        integration_mapping_id=mapping_id,
        provider=provider,
        property_id=property_id,
        mode=sync_request.mode,
        status=SyncRunStatus.QUEUED.value,
        date_range_start=sync_request.date_range_start,
        date_range_end=sync_request.date_range_end,
    )

    db.add(sync_run)
    await db.commit()
    await db.refresh(sync_run)

    return TriggerSyncResponse(
        sync_run_id=sync_run.id,
        mapping_id=mapping_id,
        status=sync_run.status,
        message=f"Sync queued successfully. Mode: {sync_request.mode}",
    )


# =============================================================================
# Property Discovery Endpoints
# =============================================================================


@router.get(
    "/integrations/{provider}/properties",
    response_model=PropertyListResponse,
    status_code=status.HTTP_200_OK,
    summary="List discovered properties",
    description="List all discovered properties for an integration provider.",
    responses={
        400: {
            "description": "Invalid provider",
        },
        401: {
            "description": "Not authenticated",
        },
    },
)
async def list_properties(
    provider: str,
    current_user: CurrentUser,
    db: DbSession,
) -> PropertyListResponse:
    """
    List all discovered properties for an integration provider.

    Returns properties that have been discovered from the provider's API.
    Use the sync endpoint to refresh the property list.

    Args:
        provider: Integration provider to list properties for.
        current_user: Current authenticated user.
        db: Database session.

    Returns:
        PropertyListResponse with list of discovered properties.
    """
    validate_provider(provider)

    # Get properties from database using singleton sync session
    sync_session = get_sync_session()
    try:
        property_service = PropertyService(sync_session)
        properties = property_service.get_user_properties(current_user.user_id, provider)

        return PropertyListResponse(
            provider=provider,
            properties=[
                IntegrationPropertyResponse(
                    id=str(p.id),
                    provider=p.provider,
                    property_id=p.property_id,
                    display_name=p.display_name,
                    property_type=p.property_type,
                    metadata=p.metadata_ or {},
                    discovered_at=p.discovered_at,
                )
                for p in properties
            ],
        )
    finally:
        sync_session.close()


# =============================================================================
# Property Sync Endpoint (FIX Issue 2)
# =============================================================================


@router.post(
    "/integrations/{provider}/properties/sync",
    response_model=PropertySyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Sync properties from provider",
    description="Trigger a sync to discover or refresh properties from the provider's API.",
    responses={
        400: {
            "description": "Invalid provider",
        },
        401: {
            "description": "Not authenticated",
        },
        404: {
            "description": "Integration not connected",
        },
    },
)
async def sync_properties(
    provider: str,
    current_user: CurrentUser,
    db: DbSession,
) -> PropertySyncResponse:
    """
    Sync properties from an integration provider.

    Calls the provider's API to discover all available properties
    and stores/updates them in the database.

    Args:
        provider: Integration provider to sync properties from.
        current_user: Current authenticated user.
        db: Database session.

    Returns:
        PropertySyncResponse with sync results.
    """
    validate_provider(provider)

    # Get existing count for comparison using singleton sync session
    sync_session = get_sync_session()
    try:
        property_service = PropertyService(sync_session)

        existing = property_service.get_user_properties(current_user.user_id, provider)
        existing_ids = {p.property_id for p in existing}

        # Sync properties using asyncio.to_thread to avoid blocking the event loop
        # The sync_properties method is async but uses sync DB operations internally
        properties = await asyncio.to_thread(
            _sync_properties_sync,
            sync_session,
            current_user.user_id,
            provider,
        )

        # Count new properties
        new_ids = {p.property_id for p in properties}
        new_count = len(new_ids - existing_ids)

        return PropertySyncResponse(
            provider=provider,
            synced_count=len(properties),
            new_count=new_count,
            message="Properties synced successfully",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    finally:
        sync_session.close()


def _sync_properties_sync(
    sync_session: Session,
    user_id: UUID,
    provider: str,
) -> list[Any]:
    """
    Synchronous wrapper for property sync to run in thread pool.

    This function runs the async sync_properties in a new event loop
    within a thread to avoid blocking the main event loop.

    Args:
        sync_session: Synchronous SQLAlchemy session.
        user_id: User UUID.
        provider: Provider name.

    Returns:
        List of synced IntegrationProperty records.
    """
    property_service = PropertyService(sync_session)

    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(property_service.sync_properties(user_id, provider))
    finally:
        loop.close()


# =============================================================================
# Property Mapping Endpoints
# =============================================================================


@router.post(
    "/projects/{project_id}/mappings",
    response_model=MappingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create property mapping",
    description="Map an integration property to a project.",
    responses={
        401: {
            "description": "Not authenticated",
        },
        404: {
            "description": "Project or property not found",
        },
        409: {
            "description": "Property already mapped to project",
        },
    },
)
async def create_mapping(
    mapping_request: MappingCreateRequest,
    project: UserProject,
) -> MappingResponse:
    """
    Create a mapping between a project and an integration property.

    Associates an integration property (e.g., a GSC site) with a project
    to enable data sync from that property.

    Args:
        mapping_request: Mapping configuration.
        project: Project retrieved via dependency (validates ownership).

    Returns:
        MappingResponse with created mapping details.
    """
    project_id = project.id

    sync_session = get_sync_session()
    try:
        mapping_service = PropertyMappingService(sync_session)

        site_id = None
        if mapping_request.site_id:
            site_id = UUID(mapping_request.site_id)

        mapping = mapping_service.create_mapping(
            project_id=project_id,
            property_id=UUID(mapping_request.property_id),
            site_id=site_id,
            is_primary=mapping_request.is_primary,
        )

        # Get property details
        property_display_name = None
        provider = None
        if mapping.integration_property:
            property_display_name = mapping.integration_property.display_name
            provider = mapping.integration_property.provider

        return MappingResponse(
            id=str(mapping.id),
            project_id=str(mapping.project_id),
            site_id=str(mapping.site_id) if mapping.site_id else None,
            property_id=str(mapping.integration_property_id),
            property_display_name=property_display_name,
            provider=provider,
            is_primary=mapping.is_primary,
            created_at=mapping.created_at,
        )
    except ValueError as e:
        error_msg = str(e)
        if "already mapped" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_msg,
        ) from e
    finally:
        sync_session.close()


@router.get(
    "/projects/{project_id}/mappings",
    response_model=MappingListResponse,
    status_code=status.HTTP_200_OK,
    summary="List project mappings",
    description="List all property mappings for a project.",
    responses={
        401: {
            "description": "Not authenticated",
        },
        404: {
            "description": "Project not found",
        },
    },
)
async def list_mappings(
    project: UserProject,
) -> MappingListResponse:
    """
    List all property mappings for a project.

    Returns all integration properties mapped to the specified project.

    Args:
        project: Project retrieved via dependency (validates ownership).

    Returns:
        MappingListResponse with list of mappings.
    """
    project_id = project.id

    sync_session = get_sync_session()
    try:
        mapping_service = PropertyMappingService(sync_session)
        mappings = mapping_service.get_project_mappings(project_id)

        return MappingListResponse(
            project_id=str(project_id),
            mappings=[
                MappingResponse(
                    id=str(m.id),
                    project_id=str(m.project_id),
                    site_id=str(m.site_id) if m.site_id else None,
                    property_id=str(m.integration_property_id),
                    property_display_name=(
                        m.integration_property.display_name if m.integration_property else None
                    ),
                    provider=m.integration_property.provider if m.integration_property else None,
                    is_primary=m.is_primary,
                    created_at=m.created_at,
                )
                for m in mappings
            ],
        )
    finally:
        sync_session.close()


@router.delete(
    "/projects/{project_id}/mappings/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete property mapping",
    description="Remove a property mapping from a project.",
    responses={
        401: {
            "description": "Not authenticated",
        },
        404: {
            "description": "Project or mapping not found",
        },
    },
)
async def delete_mapping(
    mapping_id: UUID,
    project: UserProject,
) -> None:
    """
    Delete a property mapping.

    Removes the association between a project and an integration property.
    This does not delete any synced data.

    Args:
        mapping_id: Mapping UUID.
        project: Project retrieved via dependency (validates ownership).
    """
    project_id = project.id

    sync_session = get_sync_session()
    try:
        mapping_service = PropertyMappingService(sync_session)
        deleted = mapping_service.delete_mapping(project_id, mapping_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mapping not found",
            )
    finally:
        sync_session.close()
