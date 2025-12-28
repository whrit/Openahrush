"""
Property discovery and mapping services.

Provides services for:
- Discovering properties from OAuth providers (GSC, GA4, BWT)
- Managing property-to-project mappings
- Syncing property lists from external APIs
"""

from datetime import UTC, datetime
from uuid import UUID

from semrush_core.models import IntegrationAccount, IntegrationMapping, IntegrationProperty, Project
from sqlalchemy.orm import Session

from semrush_integrations.adapters.base import DiscoveredProperty
from semrush_integrations.adapters.bwt_adapter import BWTAdapter
from semrush_integrations.adapters.ga4_adapter import GA4Adapter
from semrush_integrations.adapters.gsc_adapter import GSCAdapter
from semrush_integrations.services.token_service import TokenService

# Provider to adapter mapping
PROVIDER_ADAPTERS = {
    "google_search_console": GSCAdapter,
    "google_analytics": GA4Adapter,
    "bing_webmaster_tools": BWTAdapter,
}


class PropertyService:
    """
    Service for discovering and managing integration properties.

    Handles the discovery of properties from OAuth providers and
    stores them in the database for later mapping to projects.

    Example:
        >>> service = PropertyService(db_session)
        >>> properties = await service.discover_properties(user_id, "google_search_console")
        >>> for prop in properties:
        ...     print(f"Found: {prop.display_name}")
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize property service.

        Args:
            db: SQLAlchemy session for database operations.
        """
        self.db = db
        self.token_service = TokenService(db)

    async def discover_properties(
        self,
        user_id: UUID,
        provider: str,
    ) -> list[IntegrationProperty]:
        """
        Discover properties from a provider and store them.

        Fetches the list of properties/sites from the provider's API
        and stores them in the database, creating new records or
        updating existing ones.

        Args:
            user_id: UUID of the user.
            provider: Provider name (e.g., "google_search_console").

        Returns:
            List of IntegrationProperty records.

        Raises:
            ValueError: If provider is unknown or no account exists.
        """
        if provider not in PROVIDER_ADAPTERS:
            raise ValueError(f"Unknown provider: {provider}")

        # Get the integration account
        account = self._get_account(user_id, provider)
        if not account:
            raise ValueError(f"No integration account found for provider: {provider}")

        # Get valid access token
        access_token = self._get_access_token(account, provider)

        # Create adapter and discover properties
        adapter_class = PROVIDER_ADAPTERS[provider]
        adapter = adapter_class()
        discovered = await adapter.discover_properties(access_token)

        # Store properties
        return self._store_properties(account, provider, discovered)

    def _get_access_token(self, account: IntegrationAccount, provider: str) -> str:
        """
        Get a valid access token for the account.

        Args:
            account: Integration account.
            provider: Provider name.

        Returns:
            Valid access token string.
        """
        from semrush_integrations.oauth.google import GoogleOAuthProvider
        from semrush_integrations.oauth.microsoft import MicrosoftOAuthProvider

        # Select appropriate OAuth provider for token refresh
        if provider in ("google_search_console", "google_analytics"):
            oauth_provider = GoogleOAuthProvider(
                client_id="",  # Not needed for refresh
                client_secret="",
                redirect_uri="",
            )
        else:
            oauth_provider = MicrosoftOAuthProvider(
                client_id="",
                client_secret="",
                redirect_uri="",
            )

        return self.token_service.get_valid_token(account.id, oauth_provider)

    async def sync_properties(
        self,
        user_id: UUID,
        provider: str,
    ) -> list[IntegrationProperty]:
        """
        Sync properties from a provider, updating existing and adding new.

        Similar to discover_properties, but explicitly designed for
        periodic sync operations. Updates existing properties and
        adds any new ones discovered.

        Args:
            user_id: UUID of the user.
            provider: Provider name.

        Returns:
            Updated list of IntegrationProperty records.
        """
        # Sync is the same as discover - we always upsert
        return await self.discover_properties(user_id, provider)

    def get_user_properties(
        self,
        user_id: UUID,
        provider: str,
    ) -> list[IntegrationProperty]:
        """
        Get all stored properties for a user and provider.

        Returns properties from the database without calling the
        external API. Use sync_properties to refresh the list.

        Args:
            user_id: UUID of the user.
            provider: Provider name.

        Returns:
            List of IntegrationProperty records.
        """
        account = self._get_account(user_id, provider)
        if not account:
            return []

        return list(account.properties)

    def _get_account(self, user_id: UUID, provider: str) -> IntegrationAccount | None:
        """
        Get the integration account for a user and provider.

        Args:
            user_id: UUID of the user.
            provider: Provider name.

        Returns:
            IntegrationAccount or None if not found.
        """
        return (
            self.db.query(IntegrationAccount)
            .filter(
                IntegrationAccount.user_id == user_id,
                IntegrationAccount.provider == provider,
            )
            .first()
        )

    def _store_properties(
        self,
        account: IntegrationAccount,
        provider: str,
        discovered: list[DiscoveredProperty],
    ) -> list[IntegrationProperty]:
        """
        Store discovered properties in the database.

        Creates new property records or updates existing ones based
        on the property_id.

        Args:
            account: The integration account.
            provider: Provider name.
            discovered: List of discovered property dicts.

        Returns:
            List of stored IntegrationProperty records.
        """
        stored: list[IntegrationProperty] = []

        # Build a map of existing properties
        existing_map: dict[str, IntegrationProperty] = {}
        for prop in account.properties:
            if prop.provider == provider:
                existing_map[prop.property_id] = prop

        for prop_data in discovered:
            property_id = prop_data["property_id"]

            if property_id in existing_map:
                # Update existing property
                existing = existing_map[property_id]
                existing.display_name = prop_data["display_name"]
                existing.property_type = prop_data["property_type"]
                existing.metadata_ = prop_data["metadata"]
                stored.append(existing)
            else:
                # Create new property
                new_property = IntegrationProperty(
                    integration_account_id=account.id,
                    provider=provider,
                    property_id=property_id,
                    display_name=prop_data["display_name"],
                    property_type=prop_data["property_type"],
                    metadata_=prop_data["metadata"],
                    discovered_at=datetime.now(UTC),
                )
                self.db.add(new_property)
                stored.append(new_property)

        self.db.commit()

        # Refresh to get IDs for new properties
        for prop in stored:
            self.db.refresh(prop)

        return stored


class PropertyMappingService:
    """
    Service for managing property-to-project mappings.

    Handles creating, listing, and deleting mappings between
    integration properties and projects.

    Example:
        >>> service = PropertyMappingService(db_session)
        >>> mapping = service.create_mapping(project_id, property_id)
        >>> print(f"Mapped {mapping.integration_property.display_name}")
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize mapping service.

        Args:
            db: SQLAlchemy session for database operations.
        """
        self.db = db

    def create_mapping(
        self,
        project_id: UUID,
        property_id: UUID,
        site_id: UUID | None = None,
        is_primary: bool = False,
    ) -> IntegrationMapping:
        """
        Create a mapping between a project and an integration property.

        Args:
            project_id: UUID of the project.
            property_id: UUID of the integration property.
            site_id: Optional UUID of a specific site within the project.
            is_primary: Whether this is the primary data source.

        Returns:
            The created IntegrationMapping record.

        Raises:
            ValueError: If project or property doesn't exist, or mapping already exists.
        """
        # Verify project exists
        project = (
            self.db.query(Project)
            .filter(Project.id == project_id)
            .first()
        )
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        # Verify property exists
        integration_property = (
            self.db.query(IntegrationProperty)
            .filter(IntegrationProperty.id == property_id)
            .first()
        )
        if not integration_property:
            raise ValueError(f"Property not found: {property_id}")

        # Check for existing mapping
        existing = (
            self.db.query(IntegrationMapping)
            .filter(
                IntegrationMapping.project_id == project_id,
                IntegrationMapping.integration_property_id == property_id,
            )
            .first()
        )
        if existing:
            raise ValueError("Property is already mapped to this project")

        # If setting as primary, unset other primary mappings for this project
        if is_primary:
            self._unset_primary_mappings(project_id)

        # Create mapping
        mapping = IntegrationMapping(
            project_id=project_id,
            site_id=site_id,
            integration_property_id=property_id,
            is_primary=is_primary,
        )
        self.db.add(mapping)
        self.db.commit()
        self.db.refresh(mapping)

        return mapping

    def get_project_mappings(self, project_id: UUID) -> list[IntegrationMapping]:
        """
        Get all property mappings for a project.

        Args:
            project_id: UUID of the project.

        Returns:
            List of IntegrationMapping records.
        """
        return (
            self.db.query(IntegrationMapping)
            .filter(IntegrationMapping.project_id == project_id)
            .all()
        )

    def get_mapping(
        self,
        project_id: UUID,
        mapping_id: UUID,
    ) -> IntegrationMapping | None:
        """
        Get a specific mapping by ID.

        Args:
            project_id: UUID of the project.
            mapping_id: UUID of the mapping.

        Returns:
            IntegrationMapping or None if not found.
        """
        return (
            self.db.query(IntegrationMapping)
            .filter(
                IntegrationMapping.id == mapping_id,
                IntegrationMapping.project_id == project_id,
            )
            .first()
        )

    def delete_mapping(
        self,
        project_id: UUID,
        mapping_id: UUID,
    ) -> bool:
        """
        Delete a property mapping.

        Args:
            project_id: UUID of the project.
            mapping_id: UUID of the mapping.

        Returns:
            True if deleted, False if not found.
        """
        mapping = self.get_mapping(project_id, mapping_id)
        if not mapping:
            return False

        self.db.delete(mapping)
        self.db.commit()
        return True

    def _unset_primary_mappings(self, project_id: UUID) -> None:
        """
        Unset the primary flag on all mappings for a project.

        Used when setting a new primary mapping.

        Args:
            project_id: UUID of the project.
        """
        (
            self.db.query(IntegrationMapping)
            .filter(
                IntegrationMapping.project_id == project_id,
                IntegrationMapping.is_primary.is_(True),
            )
            .update({"is_primary": False})
        )
