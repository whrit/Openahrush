"""
Integration-related Pydantic schemas.

Provides request/response models for:
- OAuth connect flow (authorization URL generation)
- OAuth callback handling (token exchange)
- Integration status and listing
- Integration disconnection
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class IntegrationProvider(str, Enum):
    """Supported integration providers."""

    GOOGLE_SEARCH_CONSOLE = "google_search_console"
    GOOGLE_ANALYTICS = "google_analytics"
    BING_WEBMASTER_TOOLS = "bing_webmaster_tools"


# =============================================================================
# Connect Endpoint Schemas
# =============================================================================


class IntegrationConnectRequest(BaseModel):
    """
    Request for starting OAuth connect flow.

    Currently empty as no additional parameters are needed,
    but can be extended for custom redirect URIs or scopes.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {}
        }
    )


class IntegrationConnectResponse(BaseModel):
    """
    Response from connect endpoint with OAuth authorization URL.

    Attributes:
        authorization_url: URL to redirect user to for OAuth authorization.
        state: CSRF protection state token that must be verified on callback.
        provider: The provider being connected.
    """

    authorization_url: str = Field(
        ...,
        description="OAuth authorization URL for user redirect",
    )
    state: str = Field(
        ...,
        description="CSRF protection state token",
    )
    provider: str = Field(
        ...,
        description="Integration provider name",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...",
                "state": "abc123def456",
                "provider": "google_search_console",
            }
        }
    )


# =============================================================================
# Callback Endpoint Schemas
# =============================================================================


class IntegrationCallbackRequest(BaseModel):
    """
    Request for OAuth callback handling.

    Attributes:
        code: Authorization code from OAuth provider.
        state: State token for CSRF validation.
    """

    code: str = Field(
        ...,
        min_length=1,
        description="Authorization code from OAuth provider",
    )
    state: str = Field(
        ...,
        min_length=1,
        description="State token for CSRF validation",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "4/0AX4XfWj...",
                "state": "abc123def456",
            }
        }
    )


class IntegrationCallbackResponse(BaseModel):
    """
    Response from callback endpoint after successful OAuth.

    Attributes:
        provider: The provider that was connected.
        connected: Whether the connection was successful.
        provider_account_id: External account ID from the provider.
        message: Success or status message.
    """

    provider: str = Field(
        ...,
        description="Integration provider name",
    )
    connected: bool = Field(
        ...,
        description="Whether the connection was successful",
    )
    provider_account_id: str | None = Field(
        None,
        description="External account ID from the provider",
    )
    message: str = Field(
        default="Successfully connected",
        description="Success or status message",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider": "google_search_console",
                "connected": True,
                "provider_account_id": "12345678901234567890",
                "message": "Successfully connected",
            }
        }
    )


# =============================================================================
# Status Endpoint Schemas
# =============================================================================


class IntegrationStatus(BaseModel):
    """
    Status of a single integration.

    Attributes:
        provider: Integration provider name.
        connected: Whether the integration is connected.
        provider_account_id: External account ID if connected.
        connected_at: When the integration was connected.
        last_sync_at: When data was last synced.
        sync_status: Current sync status.
        sync_error: Error message if sync failed.
    """

    provider: str = Field(
        ...,
        description="Integration provider name",
    )
    connected: bool = Field(
        ...,
        description="Whether the integration is connected",
    )
    provider_account_id: str | None = Field(
        None,
        description="External account ID from the provider",
    )
    connected_at: datetime | None = Field(
        None,
        description="When the integration was connected",
    )
    last_sync_at: datetime | None = Field(
        None,
        description="When data was last synced",
    )
    sync_status: str | None = Field(
        None,
        description="Current sync status (pending, syncing, success, failed)",
    )
    sync_error: str | None = Field(
        None,
        description="Error message if sync failed",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "provider": "google_search_console",
                "connected": True,
                "provider_account_id": "12345678901234567890",
                "connected_at": "2024-01-15T10:30:00Z",
                "last_sync_at": "2024-01-15T11:00:00Z",
                "sync_status": "success",
                "sync_error": None,
            }
        }
    )


# =============================================================================
# List Endpoint Schemas
# =============================================================================


class IntegrationListResponse(BaseModel):
    """
    Response listing all connected integrations.

    Attributes:
        integrations: List of connected integrations with status.
    """

    integrations: list[IntegrationStatus] = Field(
        default_factory=list,
        description="List of connected integrations",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "integrations": [
                    {
                        "provider": "google_search_console",
                        "connected": True,
                        "provider_account_id": "12345678901234567890",
                        "connected_at": "2024-01-15T10:30:00Z",
                        "last_sync_at": "2024-01-15T11:00:00Z",
                        "sync_status": "success",
                        "sync_error": None,
                    },
                    {
                        "provider": "google_analytics",
                        "connected": True,
                        "provider_account_id": "98765432109876543210",
                        "connected_at": "2024-01-10T08:00:00Z",
                        "last_sync_at": None,
                        "sync_status": "pending",
                        "sync_error": None,
                    },
                ]
            }
        }
    )


# =============================================================================
# Disconnect Endpoint Schemas
# =============================================================================


class IntegrationDisconnectResponse(BaseModel):
    """
    Response from disconnect endpoint.

    Attributes:
        provider: The provider that was disconnected.
        message: Success message.
    """

    provider: str = Field(
        ...,
        description="Integration provider that was disconnected",
    )
    message: str = Field(
        default="Successfully disconnected",
        description="Success message",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider": "google_search_console",
                "message": "Successfully disconnected",
            }
        }
    )


# =============================================================================
# Property Discovery Schemas
# =============================================================================


class IntegrationPropertyResponse(BaseModel):
    """
    Response representing a discovered integration property.

    Attributes:
        id: Unique identifier for the property.
        provider: Integration provider name.
        property_id: External property ID from the provider.
        display_name: Human-readable name for the property.
        property_type: Provider-specific property type.
        metadata: Additional provider-specific metadata.
        discovered_at: When this property was discovered.
    """

    id: str = Field(
        ...,
        description="Unique identifier for the property",
    )
    provider: str = Field(
        ...,
        description="Integration provider name",
    )
    property_id: str = Field(
        ...,
        description="External property ID from the provider",
    )
    display_name: str | None = Field(
        None,
        description="Human-readable name for the property",
    )
    property_type: str | None = Field(
        None,
        description="Provider-specific property type",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional provider-specific metadata",
    )
    discovered_at: datetime | None = Field(
        None,
        description="When this property was discovered",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                "provider": "google_search_console",
                "property_id": "https://example.com/",
                "display_name": "example.com",
                "property_type": "url_prefix",
                "metadata": {"permission_level": "siteOwner"},
                "discovered_at": "2024-01-15T10:30:00Z",
            }
        }
    )


class PropertyListResponse(BaseModel):
    """
    Response listing discovered properties for a provider.

    Attributes:
        properties: List of discovered properties.
        provider: Integration provider name.
    """

    properties: list[IntegrationPropertyResponse] = Field(
        default_factory=list,
        description="List of discovered properties",
    )
    provider: str = Field(
        ...,
        description="Integration provider name",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider": "google_search_console",
                "properties": [
                    {
                        "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                        "provider": "google_search_console",
                        "property_id": "https://example.com/",
                        "display_name": "example.com",
                        "property_type": "url_prefix",
                        "metadata": {"permission_level": "siteOwner"},
                        "discovered_at": "2024-01-15T10:30:00Z",
                    }
                ],
            }
        }
    )


class PropertySyncResponse(BaseModel):
    """
    Response from property sync operation.

    Attributes:
        provider: Integration provider name.
        synced_count: Number of properties synced.
        new_count: Number of new properties discovered.
        message: Status message.
    """

    provider: str = Field(
        ...,
        description="Integration provider name",
    )
    synced_count: int = Field(
        ...,
        description="Total number of properties synced",
    )
    new_count: int = Field(
        0,
        description="Number of new properties discovered",
    )
    message: str = Field(
        default="Properties synced successfully",
        description="Status message",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider": "google_search_console",
                "synced_count": 5,
                "new_count": 2,
                "message": "Properties synced successfully",
            }
        }
    )


# =============================================================================
# Property Mapping Schemas
# =============================================================================


class MappingCreateRequest(BaseModel):
    """
    Request for creating a property-to-project mapping.

    Attributes:
        property_id: UUID of the integration property to map.
        site_id: Optional UUID of a specific site within the project.
        is_primary: Whether this is the primary data source for the project.
    """

    property_id: str = Field(
        ...,
        description="UUID of the integration property to map",
    )
    site_id: str | None = Field(
        None,
        description="Optional UUID of a specific site within the project",
    )
    is_primary: bool = Field(
        False,
        description="Whether this is the primary data source for the project",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "property_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                "is_primary": True,
            }
        }
    )


class MappingResponse(BaseModel):
    """
    Response representing a property-to-project mapping.

    Attributes:
        id: Unique identifier for the mapping.
        project_id: UUID of the project.
        site_id: Optional UUID of the specific site.
        property_id: UUID of the integration property.
        property_display_name: Display name of the mapped property.
        provider: Integration provider name.
        is_primary: Whether this is the primary data source.
        created_at: When this mapping was created.
    """

    id: str = Field(
        ...,
        description="Unique identifier for the mapping",
    )
    project_id: str = Field(
        ...,
        description="UUID of the project",
    )
    site_id: str | None = Field(
        None,
        description="Optional UUID of the specific site",
    )
    property_id: str = Field(
        ...,
        description="UUID of the integration property",
    )
    property_display_name: str | None = Field(
        None,
        description="Display name of the mapped property",
    )
    provider: str | None = Field(
        None,
        description="Integration provider name",
    )
    is_primary: bool = Field(
        False,
        description="Whether this is the primary data source",
    )
    created_at: datetime | None = Field(
        None,
        description="When this mapping was created",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                "project_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "site_id": None,
                "property_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                "property_display_name": "example.com",
                "provider": "google_search_console",
                "is_primary": True,
                "created_at": "2024-01-15T10:30:00Z",
            }
        }
    )


class MappingListResponse(BaseModel):
    """
    Response listing property mappings for a project.

    Attributes:
        mappings: List of property mappings.
        project_id: UUID of the project.
    """

    mappings: list[MappingResponse] = Field(
        default_factory=list,
        description="List of property mappings",
    )
    project_id: str = Field(
        ...,
        description="UUID of the project",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "mappings": [
                    {
                        "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                        "project_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "property_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                        "property_display_name": "example.com",
                        "provider": "google_search_console",
                        "is_primary": True,
                        "created_at": "2024-01-15T10:30:00Z",
                    }
                ],
            }
        }
    )
