"""
Pydantic schemas for integration data.
"""

from semrush_integrations.schemas.search_data import SearchDataRow, SearchDataResponse
from semrush_integrations.schemas.analytics_data import AnalyticsDataRow, AnalyticsDataResponse

__all__ = [
    "SearchDataRow",
    "SearchDataResponse",
    "AnalyticsDataRow",
    "AnalyticsDataResponse",
]
