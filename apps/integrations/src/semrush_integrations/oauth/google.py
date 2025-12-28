"""
Google OAuth provider for Google Search Console and Google Analytics.

Implements OAuth 2.0 flow for Google APIs including:
- Google Search Console (webmasters.readonly scope)
- Google Analytics 4 (analytics.readonly scope)
"""

from datetime import datetime, timedelta

import httpx

from semrush_integrations.oauth.base import OAuthProvider, OAuthTokens, OAuthUserInfo


class GoogleOAuthProvider(OAuthProvider):
    """
    Google OAuth 2.0 provider implementation.

    Supports OAuth authorization for Google Search Console and Google Analytics.
    Uses Google's OAuth 2.0 endpoints and includes default scopes for both services.

    Example:
        >>> provider = GoogleOAuthProvider(
        ...     client_id=os.environ["GOOGLE_CLIENT_ID"],
        ...     client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        ...     redirect_uri="https://app.example.com/oauth/google/callback",
        ... )
        >>> auth_url = provider.get_authorization_url(state_token)
        >>> # After user authorizes:
        >>> tokens = await provider.exchange_code(authorization_code)
    """

    provider_name: str = "google"
    authorization_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url: str = "https://oauth2.googleapis.com/token"
    userinfo_url: str = "https://www.googleapis.com/oauth2/v2/userinfo"
    revoke_url: str = "https://oauth2.googleapis.com/revoke"

    # Default scopes for GSC + GA4
    scopes: list[str] = [
        "openid",
        "email",
        "https://www.googleapis.com/auth/webmasters.readonly",
        "https://www.googleapis.com/auth/analytics.readonly",
    ]

    async def exchange_code(self, code: str) -> OAuthTokens:
        """
        Exchange authorization code for access and refresh tokens.

        Makes a POST request to Google's token endpoint with the authorization
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

        Makes a POST request to Google's token endpoint with the refresh token.
        Note that Google may or may not return a new refresh token - if not,
        the original refresh token is preserved.

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
        Retrieve user information from Google's userinfo endpoint.

        Args:
            access_token: Valid access token.

        Returns:
            OAuthUserInfo with user's Google ID, email, and name.

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

            return OAuthUserInfo(
                external_id=data["id"],
                email=data.get("email"),
                name=data.get("name"),
            )

    async def revoke_token(self, token: str) -> bool:
        """
        Revoke an access or refresh token.

        Makes a POST request to Google's revocation endpoint.
        Can be used to revoke either access tokens or refresh tokens.

        Args:
            token: The token to revoke.

        Returns:
            True if revocation succeeded, False otherwise.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.revoke_url,
                params={"token": token},
            )
            return response.status_code == 200
