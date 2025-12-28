"""
Google Analytics 4 property discovery adapter.

Discovers GA4 accounts and properties that a user has access to via
the GA4 Admin API.
"""

from typing import Any

import httpx

from semrush_integrations.adapters.base import DiscoveredProperty, PropertyAdapter


class GA4Adapter(PropertyAdapter):
    """
    Google Analytics 4 property discovery adapter.

    Fetches accounts and properties from the GA4 Admin API and
    normalizes them into the standard property format.

    GA4 has a hierarchy:
    - Accounts (organizational unit)
    - Properties (data containers, what we want to discover)

    Example:
        >>> adapter = GA4Adapter()
        >>> properties = await adapter.discover_properties(access_token)
        >>> for prop in properties:
        ...     print(f"{prop['display_name']} (Account: {prop['metadata']['account_name']})")
    """

    provider_name = "google_analytics"

    # Google Analytics Admin API endpoint
    API_BASE_URL = "https://analyticsadmin.googleapis.com/v1beta"

    async def discover_properties(self, access_token: str) -> list[DiscoveredProperty]:
        """
        Discover all GA4 properties accessible with the given access token.

        First fetches all accounts, then fetches properties for each account.
        Handles pagination for large property lists.

        Args:
            access_token: Valid Google OAuth access token with
                         analytics.readonly scope.

        Returns:
            List of discovered GA4 properties.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        # First, get all accounts
        accounts_response = await self._fetch_accounts(access_token)
        accounts = accounts_response.get("accounts", [])

        if not accounts:
            return []

        # Build account lookup map
        account_map: dict[str, str] = {}
        for account in accounts:
            account_id = account.get("name", "")
            account_name = account.get("displayName", "Unknown Account")
            account_map[account_id] = account_name

        # Fetch all properties with pagination
        all_properties: list[DiscoveredProperty] = []
        page_token: str | None = None

        while True:
            properties_response = await self._fetch_properties(access_token, page_token)

            ga4_properties = properties_response.get("properties", [])
            for prop in ga4_properties:
                property_id = prop.get("name", "")
                display_name = prop.get("displayName", "Unknown Property")
                parent_account = prop.get("parent", "")
                property_type = prop.get("propertyType", "PROPERTY_TYPE_ORDINARY")

                # Look up account name
                account_name = account_map.get(parent_account, "Unknown Account")

                all_properties.append(
                    DiscoveredProperty(
                        property_id=property_id,
                        display_name=display_name,
                        property_type=property_type.lower(),
                        metadata={
                            "account_id": parent_account,
                            "account_name": account_name,
                            "industry_category": prop.get("industryCategory"),
                            "time_zone": prop.get("timeZone"),
                            "currency_code": prop.get("currencyCode"),
                            "create_time": prop.get("createTime"),
                        },
                    )
                )

            # Check for next page
            page_token = properties_response.get("nextPageToken")
            if not page_token:
                break

        return all_properties

    async def _fetch_accounts(self, access_token: str) -> dict[str, Any]:
        """
        Fetch accounts list from the GA4 Admin API.

        Args:
            access_token: Valid OAuth access token.

        Returns:
            API response as dictionary.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/accounts",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

    async def _fetch_properties(
        self,
        access_token: str,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch properties list from the GA4 Admin API.

        Args:
            access_token: Valid OAuth access token.
            page_token: Optional pagination token for subsequent pages.

        Returns:
            API response as dictionary.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        params: dict[str, str] = {
            "filter": "parent:accounts/-",  # Get properties from all accounts
        }
        if page_token:
            params["pageToken"] = page_token

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/properties",
                params=params,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
