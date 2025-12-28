"""
Google Search Console property discovery adapter.

Discovers GSC sites/properties that a user has access to via
the Search Console API (sites.list endpoint).
"""

from typing import Any

import httpx

from semrush_integrations.adapters.base import DiscoveredProperty, PropertyAdapter


class GSCAdapter(PropertyAdapter):
    """
    Google Search Console property discovery adapter.

    Fetches sites from the Search Console API and normalizes them
    into the standard property format.

    GSC has two types of properties:
    - URL-prefix properties: https://example.com/
    - Domain properties: sc-domain:example.com

    Example:
        >>> adapter = GSCAdapter()
        >>> properties = await adapter.discover_properties(access_token)
        >>> for prop in properties:
        ...     print(f"{prop['display_name']} ({prop['property_type']})")
    """

    provider_name = "google_search_console"

    # Google Search Console API endpoint
    API_BASE_URL = "https://www.googleapis.com/webmasters/v3"

    async def discover_properties(self, access_token: str) -> list[DiscoveredProperty]:
        """
        Discover all GSC sites accessible with the given access token.

        Calls the Search Console sites.list() API and transforms the
        response into standardized property format.

        Args:
            access_token: Valid Google OAuth access token with
                         webmasters.readonly scope.

        Returns:
            List of discovered GSC properties.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        response_data = await self._fetch_sites(access_token)

        site_entries = response_data.get("siteEntry", [])
        if not site_entries:
            return []

        properties: list[DiscoveredProperty] = []
        for entry in site_entries:
            site_url = entry.get("siteUrl", "")
            permission_level = entry.get("permissionLevel", "unknown")

            # Determine property type
            if site_url.startswith("sc-domain:"):
                property_type = "domain"
            else:
                property_type = "url_prefix"

            # Extract display name from URL
            display_name = self._extract_domain_from_url(site_url)

            properties.append(
                DiscoveredProperty(
                    property_id=site_url,
                    display_name=display_name,
                    property_type=property_type,
                    metadata={
                        "permission_level": permission_level,
                    },
                )
            )

        return properties

    async def _fetch_sites(self, access_token: str) -> dict[str, Any]:
        """
        Fetch sites list from the Search Console API.

        Args:
            access_token: Valid OAuth access token.

        Returns:
            API response as dictionary.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/sites",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
