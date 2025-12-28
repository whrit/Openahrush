"""
Pydantic schemas for normalized analytics data.

These schemas represent web analytics data from Google Analytics 4
and other analytics providers in a unified format that maps to analytics_fact_daily.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class AnalyticsDataRow(BaseModel):
    """
    A single row of normalized analytics data.

    Represents web analytics metrics for a specific date and dimension
    combination. All fields are optional except date and sessions to
    support different granularities of data.

    Attributes:
        date: Date of the metrics.
        page_url: Page path/URL.
        sessions: Number of sessions.
        users: Number of unique users.
        engagement_rate: GA4 engagement rate (0.0000 to 1.0000).
        conversions: Number of conversion events.
        revenue: Revenue amount (e-commerce).
        country: ISO country code.
        device: Device category (desktop, mobile, tablet).
        source_medium: Traffic source/medium combination.
        campaign: Marketing campaign name.
    """

    date: date
    page_url: str | None = None
    sessions: int = Field(ge=0)
    users: int | None = Field(default=None, ge=0)
    engagement_rate: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    conversions: int | None = Field(default=None, ge=0)
    revenue: Decimal | None = Field(default=None, ge=Decimal("0"))
    country: str | None = None
    device: str | None = None
    source_medium: str | None = None
    campaign: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "date": "2024-01-01",
                    "page_url": "/page",
                    "sessions": 100,
                    "users": 80,
                    "engagement_rate": "0.6500",
                    "conversions": 10,
                    "revenue": "500.00",
                    "country": "usa",
                    "device": "desktop",
                    "source_medium": "google / organic",
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


class AnalyticsDataResponse(BaseModel):
    """
    Container for analytics data response from an adapter.

    Wraps a list of AnalyticsDataRow objects with metadata about the response.

    Attributes:
        rows: List of analytics data rows.
        total_rows: Total number of rows (may differ from len(rows) if paginated).
        sampling_info: Information about data sampling if applicable.
        data_quality_flags: Any quality indicators from the API.
    """

    rows: list[AnalyticsDataRow] = Field(default_factory=list)
    total_rows: int = 0
    sampling_info: dict[str, str] | None = None
    data_quality_flags: dict[str, str] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "rows": [
                        {
                            "date": "2024-01-01",
                            "page_url": "/page",
                            "sessions": 100,
                            "users": 80,
                        }
                    ],
                    "total_rows": 1,
                }
            ]
        }
    }
