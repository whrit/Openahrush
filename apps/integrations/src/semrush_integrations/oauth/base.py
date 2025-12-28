"""
Base OAuth provider class and data types.

Provides abstract base class for OAuth 2.0 provider implementations
with common authorization flow handling.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode


@dataclass
class OAuthTokens:
    """
    OAuth token response data.

    Holds tokens received from OAuth provider after authorization
    code exchange or token refresh.

    Attributes:
        access_token: The access token for API requests.
        refresh_token: The refresh token for obtaining new access tokens.
                      May be None if not provided by the provider.
        token_type: Token type, typically "Bearer".
        expires_at: When the access token expires. None if not provided.
        scopes: List of scopes granted for this token.
    """

    access_token: str
    refresh_token: str | None
    token_type: str
    expires_at: datetime | None
    scopes: list[str]


@dataclass
class OAuthUserInfo:
    """
    User information from OAuth provider.

    Contains basic user identity information retrieved from the provider.

    Attributes:
        external_id: The user's ID on the external provider.
        email: User's email address if available.
        name: User's display name if available.
    """

    external_id: str
    email: str | None
    name: str | None


class OAuthProvider(ABC):
    """
    Abstract base class for OAuth 2.0 providers.

    Provides common OAuth flow functionality and defines the interface
    that concrete provider implementations must implement.

    Class Attributes:
        provider_name: Unique identifier for this provider (e.g., "google", "microsoft").
        authorization_url: URL for the OAuth authorization endpoint.
        token_url: URL for the OAuth token endpoint.
        scopes: Default list of scopes to request.

    Example:
        >>> class MyProvider(OAuthProvider):
        ...     provider_name = "my_provider"
        ...     authorization_url = "https://provider.com/oauth/authorize"
        ...     token_url = "https://provider.com/oauth/token"
        ...     scopes = ["read", "write"]
        ...
        ...     async def exchange_code(self, code: str) -> OAuthTokens:
        ...         # Implementation
        ...         pass
    """

    provider_name: str
    authorization_url: str
    token_url: str
    scopes: list[str]

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        """
        Initialize OAuth provider with client credentials.

        Args:
            client_id: OAuth client ID from provider.
            client_secret: OAuth client secret from provider.
            redirect_uri: Callback URL for OAuth flow.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_authorization_url(self, state: str) -> str:
        """
        Generate the OAuth authorization URL.

        Creates a URL that the user should be redirected to for authorization.
        Includes all required OAuth parameters including:
        - client_id
        - redirect_uri
        - response_type (code)
        - scope
        - state (CSRF protection)
        - access_type (offline for refresh tokens)
        - prompt (consent to ensure refresh token is returned)

        Args:
            state: CSRF protection state token.

        Returns:
            Complete authorization URL with all parameters.

        Example:
            >>> url = provider.get_authorization_url("csrf_state_token")
            >>> # Redirect user to this URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        query_string = urlencode(params)
        return f"{self.authorization_url}?{query_string}"

    @abstractmethod
    async def exchange_code(self, code: str) -> OAuthTokens:
        """
        Exchange authorization code for access and refresh tokens.

        Called after the user authorizes the application and is redirected
        back with an authorization code.

        Args:
            code: Authorization code from OAuth callback.

        Returns:
            OAuthTokens containing access token, refresh token, and metadata.

        Raises:
            httpx.HTTPStatusError: If the token exchange request fails.
        """
        pass

    @abstractmethod
    async def refresh_tokens(self, refresh_token: str) -> OAuthTokens:
        """
        Refresh expired access token using refresh token.

        Args:
            refresh_token: The refresh token from a previous token response.

        Returns:
            OAuthTokens containing new access token and possibly new refresh token.

        Raises:
            httpx.HTTPStatusError: If the refresh request fails.
        """
        pass

    @abstractmethod
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """
        Retrieve user information from the OAuth provider.

        Args:
            access_token: Valid access token.

        Returns:
            OAuthUserInfo with user's external ID, email, and name.

        Raises:
            httpx.HTTPStatusError: If the user info request fails.
        """
        pass

    @abstractmethod
    async def revoke_token(self, token: str) -> bool:
        """
        Revoke an access or refresh token.

        Should be called when disconnecting an integration to properly
        clean up authorization on the provider's side.

        Args:
            token: The token to revoke.

        Returns:
            True if revocation succeeded, False otherwise.
        """
        pass
