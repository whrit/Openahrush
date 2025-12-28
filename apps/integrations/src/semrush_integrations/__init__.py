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

Note: This is a placeholder package. Full implementation pending.
"""

__version__ = "0.1.0"

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
