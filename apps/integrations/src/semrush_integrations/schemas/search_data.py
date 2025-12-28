"""
Pydantic schemas for normalized search data.

These schemas represent search performance data from Google Search Console
and Bing Webmaster Tools in a unified format that maps to search_fact_daily.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class SearchDataRow(BaseModel):
    """
    A single row of normalized search data.

    Represents search performance metrics for a specific date and dimension
    combination. All fields are optional except date, clicks, and impressions
    to support different granularities of data.

    Attributes:
        date: Date of the metrics.
        query: Search query text (optional for page-level aggregation).
        page_url: Page URL (optional for query-level aggregation).
        clicks: Number of clicks from search results.
        impressions: Number of times shown in search results.
        ctr: Click-through rate (0.0000 to 1.0000).
        position: Average ranking position.
        device: Device type (desktop, mobile, tablet).
        country: ISO country code.
        search_type: Search type (web, image, video, news, discover).
    """

    date: date
    query: str | None = None
    page_url: str | None = None
    clicks: int = Field(ge=0)
    impressions: int = Field(ge=0)
    ctr: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    position: Decimal | None = Field(default=None, ge=Decimal("0"))
    device: str | None = None
    country: str | None = None
    search_type: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "date": "2024-01-01",
                    "query": "example search query",
                    "page_url": "https://example.com/page",
                    "clicks": 100,
                    "impressions": 1000,
                    "ctr": "0.1000",
                    "position": "3.50",
                    "device": "desktop",
                    "country": "usa",
                    "search_type": "web",
                }
            ]
        }
    }

    @field_validator("device", mode="before")
    @classmethod
    def normalize_device(cls, v: str | None) -> str | None:
        """Normalize device type to lowercase."""
        if v is not None:
            return v.lower()
        return v

    @field_validator("country", mode="before")
    @classmethod
    def normalize_country(cls, v: str | None) -> str | None:
        """Normalize country code to lowercase."""
        if v is not None:
            return v.lower()
        return v

    @field_validator("search_type", mode="before")
    @classmethod
    def normalize_search_type(cls, v: str | None) -> str | None:
        """Normalize search type to lowercase."""
        if v is not None:
            return v.lower()
        return v


class SearchDataResponse(BaseModel):
    """
    Container for search data response from an adapter.

    Wraps a list of SearchDataRow objects with metadata about the response.

    Attributes:
        rows: List of search data rows.
        total_rows: Total number of rows (may differ from len(rows) if paginated).
        response_aggregation_type: How the data was aggregated (e.g., byProperty).
        data_quality_flags: Any quality indicators from the API.
    """

    rows: list[SearchDataRow] = Field(default_factory=list)
    total_rows: int = 0
    response_aggregation_type: str | None = None
    data_quality_flags: dict[str, str] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "rows": [
                        {
                            "date": "2024-01-01",
                            "query": "test",
                            "clicks": 10,
                            "impressions": 100,
                        }
                    ],
                    "total_rows": 1,
                    "response_aggregation_type": "byProperty",
                }
            ]
        }
    }
