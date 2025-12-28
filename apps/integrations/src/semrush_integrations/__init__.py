"""
Openahrush Integrations.

Third-party integration support for:
- Google Search Console (GSC)
- Google Analytics 4 (GA4)
- Bing Webmaster Tools (BWT)
- Custom webhook integrations

Provides:
- OAuth2 authentication flows
- Data sync and normalization
- Token refresh and management
"""

from semrush_integrations.oauth.base import OAuthProvider, OAuthTokens, OAuthUserInfo
from semrush_integrations.oauth.google import GoogleOAuthProvider
from semrush_integrations.oauth.microsoft import MicrosoftOAuthProvider
from semrush_integrations.services.token_service import TokenService

__version__ = "0.1.0"

__all__ = [
    # OAuth base
    "OAuthProvider",
    "OAuthTokens",
    "OAuthUserInfo",
    # OAuth providers
    "GoogleOAuthProvider",
    "MicrosoftOAuthProvider",
    # Services
    "TokenService",
    # Utilities
    "register_provider",
    "get_provider",
    "PROVIDERS",
]

# Integration providers will be registered here
PROVIDERS: dict[str, type] = {}


def register_provider(name: str):
    """
    Decorator to register an integration provider.

    Args:
        name: Provider identifier (e.g., "google_search_console").

    Example:
        @register_provider("google_search_console")
        class GoogleSearchConsoleProvider:
            ...
    """

    def decorator(cls: type) -> type:
        PROVIDERS[name] = cls
        return cls

    return decorator


def get_provider(name: str) -> type | None:
    """
    Get a registered integration provider.

    Args:
        name: Provider identifier.

    Returns:
        Provider class or None if not found.
    """
    return PROVIDERS.get(name)
