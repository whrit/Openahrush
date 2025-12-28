"""
OAuth providers for Openahrush integrations.

Provides:
- Base OAuth provider class with common functionality
- Google OAuth provider (GSC, GA4)
- Microsoft OAuth provider (Bing Webmaster Tools)
"""

from semrush_integrations.oauth.base import OAuthProvider, OAuthTokens, OAuthUserInfo
from semrush_integrations.oauth.google import GoogleOAuthProvider
from semrush_integrations.oauth.microsoft import MicrosoftOAuthProvider

__all__ = [
    "GoogleOAuthProvider",
    "MicrosoftOAuthProvider",
    "OAuthProvider",
    "OAuthTokens",
    "OAuthUserInfo",
]
