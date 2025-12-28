"""
Data adapters for fetching SEO data from external providers.

These adapters fetch actual SEO data (search performance, analytics) as opposed
to property discovery adapters which just list available properties.
"""

from semrush_integrations.adapters.data.base import DataAdapter, DateRange
from semrush_integrations.adapters.data.gsc_data import GSCDataAdapter
from semrush_integrations.adapters.data.ga4_data import GA4DataAdapter
from semrush_integrations.adapters.data.bwt_data import BWTDataAdapter

__all__ = [
    "DataAdapter",
    "DateRange",
    "GSCDataAdapter",
    "GA4DataAdapter",
    "BWTDataAdapter",
]
