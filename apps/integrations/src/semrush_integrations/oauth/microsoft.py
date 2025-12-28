"""
Microsoft OAuth provider for Bing Webmaster Tools.

Implements OAuth 2.0 flow for Microsoft identity platform (Azure AD v2.0)
for accessing Bing Webmaster Tools API.
"""

from datetime import datetime, timedelta

import httpx

from semrush_integrations.oauth.base import OAuthProvider, OAuthTokens, OAuthUserInfo


class MicrosoftOAuthProvider(OAuthProvider):
    """
    Microsoft OAuth 2.0 provider implementation.

    Supports OAuth authorization for Microsoft services via Azure AD v2.0.
    Uses the common endpoint which allows both personal Microsoft accounts
    and work/school accounts.

    Example:
        >>> provider = MicrosoftOAuthProvider(
        ...     client_id=os.environ["MICROSOFT_CLIENT_ID"],
        ...     client_secret=os.environ["MICROSOFT_CLIENT_SECRET"],
        ...     redirect_uri="https://app.example.com/oauth/microsoft/callback",
        ... )
        >>> auth_url = provider.get_authorization_url(state_token)
        >>> # After user authorizes:
        >>> tokens = await provider.exchange_code(authorization_code)
    """

    provider_name: str = "microsoft"
    authorization_url: str = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    token_url: str = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    userinfo_url: str = "https://graph.microsoft.com/v1.0/me"

    # Default scopes for Microsoft identity and Bing Webmaster Tools
    scopes: list[str] = [
        "openid",
        "email",
        "profile",
        "offline_access",  # Required for refresh tokens with Microsoft
    ]

    async def exchange_code(self, code: str) -> OAuthTokens:
        """
        Exchange authorization code for access and refresh tokens.

        Makes a POST request to Microsoft's token endpoint with the authorization
        code and client credentials.

        Args:
            code: Authorization code from OAuth callback.

        Returns:
            OAuthTokens containing access token, refresh token, and expiry.

        Raises:
            httpx.HTTPStatusError: If the token exchange fails.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
            )
            response.raise_for_status()
            data = response.json()

            expires_at = None
            if "expires_in" in data:
                expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])

            return OAuthTokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                token_type=data.get("token_type", "Bearer"),
                expires_at=expires_at,
                scopes=data.get("scope", "").split(),
            )

    async def refresh_tokens(self, refresh_token: str) -> OAuthTokens:
        """
        Refresh expired access token using refresh token.

        Makes a POST request to Microsoft's token endpoint with the refresh token.
        Note that Microsoft typically returns a new refresh token with each refresh.

        Args:
            refresh_token: The refresh token from a previous token response.

        Returns:
            OAuthTokens containing new access token and refresh token.

        Raises:
            httpx.HTTPStatusError: If the refresh request fails.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            data = response.json()

            expires_at = None
            if "expires_in" in data:
                expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])

            return OAuthTokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", refresh_token),
                token_type=data.get("token_type", "Bearer"),
                expires_at=expires_at,
                scopes=data.get("scope", "").split(),
            )

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """
        Retrieve user information from Microsoft Graph API.

        Args:
            access_token: Valid access token.

        Returns:
            OAuthUserInfo with user's Microsoft ID, email, and name.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()

            # Microsoft uses 'mail' for email, falling back to 'userPrincipalName'
            email = data.get("mail") or data.get("userPrincipalName")

            return OAuthUserInfo(
                external_id=data["id"],
                email=email,
                name=data.get("displayName"),
            )

    async def revoke_token(self, token: str) -> bool:
        """
        Revoke an access or refresh token.

        Note: Microsoft does not provide a public token revocation endpoint.
        Tokens must be revoked through the Azure portal or will expire naturally.
        This method returns True to indicate the operation completed (no-op).

        For actual revocation, users should:
        1. Wait for token expiry
        2. Use Azure AD admin portal to revoke sessions
        3. Clear tokens from local storage

        Args:
            token: The token to revoke (not used).

        Returns:
            True (revocation is not supported via API).
        """
        # Microsoft doesn't have a public token revocation endpoint
        # The token will expire naturally or be revoked via Azure portal
        return True
