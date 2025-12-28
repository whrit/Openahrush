"""
Pydantic schemas for integration data.
"""

from semrush_integrations.schemas.analytics_data import AnalyticsDataResponse, AnalyticsDataRow
from semrush_integrations.schemas.search_data import SearchDataResponse, SearchDataRow

__all__ = [
    "AnalyticsDataResponse",
    "AnalyticsDataRow",
    "SearchDataResponse",
    "SearchDataRow",
]
