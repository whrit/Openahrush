"""
Openahrush Reports.

Report generation and export capabilities:
- PDF report rendering
- CSV/Excel exports
- Scheduled report delivery
- Custom report templates

Note: This is a placeholder package. Full implementation pending.
"""

__version__ = "0.1.0"

from enum import StrEnum


class ReportFormat(StrEnum):
    """Supported report export formats."""

    PDF = "pdf"
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"


class ReportType(StrEnum):
    """Types of reports that can be generated."""

    SITE_AUDIT = "site_audit"
    BACKLINK_PROFILE = "backlink_profile"
    KEYWORD_RANKING = "keyword_ranking"
    TRAFFIC_ANALYSIS = "traffic_analysis"
    COMPETITOR_COMPARISON = "competitor_comparison"
