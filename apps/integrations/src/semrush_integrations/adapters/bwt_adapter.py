"""
Bing Webmaster Tools property discovery adapter.

Discovers BWT sites that a user has access to via the Bing Webmaster Tools API.
"""

from typing import Any

import httpx

from semrush_integrations.adapters.base import DiscoveredProperty, PropertyAdapter


class BWTAdapter(PropertyAdapter):
    """
    Bing Webmaster Tools property discovery adapter.

    Fetches sites from the BWT API and normalizes them into the
    standard property format.

    Example:
        >>> adapter = BWTAdapter()
        >>> properties = await adapter.discover_properties(access_token)
        >>> for prop in properties:
        ...     verified = "Verified" if prop['metadata']['is_verified'] else "Unverified"
        ...     print(f"{prop['display_name']} ({verified})")
    """

    provider_name = "bing_webmaster_tools"

    # Bing Webmaster Tools API endpoint
    API_BASE_URL = "https://ssl.bing.com/webmaster/api.svc/json"

    async def discover_properties(self, access_token: str) -> list[DiscoveredProperty]:
        """
        Discover all BWT sites accessible with the given access token.

        Calls the GetUserSites API and transforms the response into
        standardized property format.

        Args:
            access_token: Valid Microsoft OAuth access token.

        Returns:
            List of discovered BWT properties.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        sites = await self._fetch_sites(access_token)

        if not sites:
            return []

        properties: list[DiscoveredProperty] = []
        for site in sites:
            site_url = site.get("Url", "")
            is_verified = site.get("IsVerified", False)
            verification_date = site.get("VerificationDate")

            # Extract display name from URL
            display_name = self._extract_domain_from_url(site_url)

            properties.append(
                DiscoveredProperty(
                    property_id=site_url,
                    display_name=display_name,
                    property_type="site",
                    metadata={
                        "is_verified": is_verified,
                        "verification_date": verification_date,
                    },
                )
            )

        return properties

    async def _fetch_sites(self, access_token: str) -> list[dict[str, Any]]:
        """
        Fetch sites list from the BWT API.

        Args:
            access_token: Valid OAuth access token.

        Returns:
            List of site dictionaries from the API.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/GetUserSites",
                params={"apikey": access_token},
                headers={
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()

            # BWT API returns a JSON array directly
            data: Any = response.json()

            # Handle both direct array response and wrapped response
            if isinstance(data, list):
                return list(data)
            elif isinstance(data, dict):
                result = data.get("d", [])
                return list(result) if isinstance(result, list) else []
            return []
