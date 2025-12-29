"""
Openahrush Reports.

Report generation and export capabilities:
- PDF report rendering with WeasyPrint
- CSV/JSON exports with streaming support
- MinIO/S3 artifact storage
- Custom report templates
- Chart generation with matplotlib

Modules:
- csv_export: CSV export generation
- json_export: JSON export generation
- pdf_report: PDF report rendering
- storage: MinIO/S3 storage service
- charts: Chart generation for reports
- builders: Report context data builders
"""

__version__ = "0.1.0"

from enum import StrEnum

from semrush_reports.builders import (
    build_audit_context,
    build_backlinks_context,
    build_overview_context,
    build_performance_context,
)
from semrush_reports.charts import (
    ChartGenerator,
    generate_bar_chart,
    generate_line_chart,
    generate_pie_chart,
)
from semrush_reports.csv_export import CSVExporter
from semrush_reports.json_export import JSONExporter
from semrush_reports.pdf_report import PDFRenderer, PDFReportService, ReportBuilder
from semrush_reports.storage import ExportStorage, MinIOStorage, StorageError


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


__all__ = [
    # Enums
    "ReportFormat",
    "ReportType",
    # CSV Export
    "CSVExporter",
    # JSON Export
    "JSONExporter",
    # PDF Reports
    "PDFRenderer",
    "PDFReportService",
    "ReportBuilder",
    # Charts
    "ChartGenerator",
    "generate_pie_chart",
    "generate_line_chart",
    "generate_bar_chart",
    # Builders
    "build_audit_context",
    "build_performance_context",
    "build_backlinks_context",
    "build_overview_context",
    # Storage
    "MinIOStorage",
    "ExportStorage",
    "StorageError",
]
