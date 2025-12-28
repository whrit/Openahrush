"""
Property discovery adapters for integration providers.

Provides adapters for discovering properties from:
- Google Search Console (GSC)
- Google Analytics 4 (GA4)
- Bing Webmaster Tools (BWT)
"""

from semrush_integrations.adapters.base import DiscoveredProperty, PropertyAdapter
from semrush_integrations.adapters.bwt_adapter import BWTAdapter
from semrush_integrations.adapters.ga4_adapter import GA4Adapter
from semrush_integrations.adapters.gsc_adapter import GSCAdapter

__all__ = [
    "BWTAdapter",
    "DiscoveredProperty",
    "GA4Adapter",
    "GSCAdapter",
    "PropertyAdapter",
]
