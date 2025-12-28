"""
Base property adapter abstract class.

Defines the interface that all property discovery adapters must implement.
Each adapter handles discovering properties from a specific provider.
"""

from abc import ABC, abstractmethod
from typing import Any, TypedDict


class DiscoveredProperty(TypedDict):
    """
    Represents a property discovered from an integration provider.

    Attributes:
        property_id: Unique identifier for the property on the provider.
        display_name: Human-readable name for the property.
        property_type: Provider-specific property type.
        metadata: Additional provider-specific metadata.
    """

    property_id: str
    display_name: str
    property_type: str
    metadata: dict[str, Any]


class PropertyAdapter(ABC):
    """
    Abstract base class for property discovery adapters.

    Each integration provider (GSC, GA4, BWT) has an adapter that knows
    how to fetch and parse the list of properties/sites available to
    an authenticated user.

    Class Attributes:
        provider_name: Unique identifier for this provider (e.g., "google_search_console").

    Example:
        >>> class MyAdapter(PropertyAdapter):
        ...     provider_name = "my_provider"
        ...
        ...     async def discover_properties(self, access_token: str) -> list[DiscoveredProperty]:
        ...         # Implementation
        ...         pass
    """

    provider_name: str

    @abstractmethod
    async def discover_properties(self, access_token: str) -> list[DiscoveredProperty]:
        """
        Discover all properties accessible with the given access token.

        Fetches the list of properties/sites from the provider's API
        and normalizes them into a standard format.

        Args:
            access_token: Valid OAuth access token for the provider.

        Returns:
            List of discovered properties with standardized fields.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        pass

    def _extract_domain_from_url(self, url: str) -> str:
        """
        Extract the domain from a URL for display purposes.

        Args:
            url: Full URL or domain property string.

        Returns:
            Clean domain name without protocol or path.

        Example:
            >>> adapter._extract_domain_from_url("https://example.com/path")
            'example.com'
            >>> adapter._extract_domain_from_url("sc-domain:example.org")
            'example.org'
        """
        # Handle Search Console domain properties
        if url.startswith("sc-domain:"):
            return url.replace("sc-domain:", "")

        # Handle regular URLs
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path

        # Remove www. prefix if present
        if domain.startswith("www."):
            domain = domain[4:]

        # Remove trailing slashes and paths
        domain = domain.rstrip("/").split("/")[0]

        return domain
