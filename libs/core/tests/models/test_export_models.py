"""
Tests for Export and ExportSchedule models.

Following TDD: These tests verify the export infrastructure models.

Tests cover:
- Export: Export job tracking with MinIO artifact storage
- ExportSchedule: Recurring export configuration with cron support

Note: Tests that require database operations are marked with pytest.mark.db
and require a PostgreSQL database to run (SQLite doesn't support JSONB/ARRAY).
"""

from datetime import UTC, datetime, timedelta

from semrush_core.models.export import (
    Export,
    ExportFormat,
    ExportResource,
    ExportSchedule,
    ExportStatus,
)

# =============================================================================
# ExportFormat Enum Tests
# =============================================================================


class TestExportFormatEnum:
    """Tests for the ExportFormat enum."""

    def test_export_format_values(self):
        """ExportFormat enum should have expected values."""
        expected_formats = ["csv", "json", "pdf"]
        actual_formats = [f.value for f in ExportFormat]
        assert sorted(actual_formats) == sorted(expected_formats)

    def test_export_format_is_string_enum(self):
        """ExportFormat should be a string enum for database storage."""
        assert ExportFormat.CSV.value == "csv"
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.PDF.value == "pdf"


# =============================================================================
# ExportResource Enum Tests
# =============================================================================


class TestExportResourceEnum:
    """Tests for the ExportResource enum."""

    def test_export_resource_values(self):
        """ExportResource enum should have expected values."""
        expected_resources = ["issues", "backlinks", "pages", "performance", "full_report"]
        actual_resources = [r.value for r in ExportResource]
        assert sorted(actual_resources) == sorted(expected_resources)

    def test_export_resource_is_string_enum(self):
        """ExportResource should be a string enum for database storage."""
        assert ExportResource.ISSUES.value == "issues"
        assert ExportResource.BACKLINKS.value == "backlinks"
        assert ExportResource.FULL_REPORT.value == "full_report"


# =============================================================================
# ExportStatus Enum Tests
# =============================================================================


class TestExportStatusEnum:
    """Tests for the ExportStatus enum."""

    def test_export_status_values(self):
        """ExportStatus enum should have expected values."""
        expected_statuses = ["queued", "running", "completed", "failed"]
        actual_statuses = [s.value for s in ExportStatus]
        assert sorted(actual_statuses) == sorted(expected_statuses)

    def test_export_status_is_string_enum(self):
        """ExportStatus should be a string enum for database storage."""
        assert ExportStatus.QUEUED.value == "queued"
        assert ExportStatus.RUNNING.value == "running"
        assert ExportStatus.COMPLETED.value == "completed"
        assert ExportStatus.FAILED.value == "failed"


# =============================================================================
# Export Model Tests
# =============================================================================


class TestExportModel:
    """Tests for the Export model."""

    def test_export_has_required_fields(self):
        """Export should have all required fields."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.QUEUED.value,
        )

        assert export.format == "csv"
        assert export.resource == "issues"
        assert export.status == "queued"

    def test_export_has_params_field(self):
        """Export should have params JSONB field."""
        params = {
            "date_from": "2025-01-01",
            "date_to": "2025-01-31",
            "filters": {"severity": "high"},
        }
        export = Export(
            format=ExportFormat.JSON.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.QUEUED.value,
            params=params,
        )

        assert export.params["date_from"] == "2025-01-01"
        assert export.params["filters"]["severity"] == "high"

    def test_export_has_artifact_fields(self):
        """Export should have artifact storage fields."""
        export = Export(
            format=ExportFormat.PDF.value,
            resource=ExportResource.FULL_REPORT.value,
            status=ExportStatus.COMPLETED.value,
            artifact_key="exports/abc123/report.pdf",
            file_size_bytes=1048576,  # 1 MB
        )

        assert export.artifact_key == "exports/abc123/report.pdf"
        assert export.file_size_bytes == 1048576

    def test_export_has_download_fields(self):
        """Export should have download URL fields."""
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.BACKLINKS.value,
            status=ExportStatus.COMPLETED.value,
            download_url="https://storage.example.com/exports/file.csv?signature=abc",
            download_expires_at=expires_at,
        )

        assert export.download_url is not None
        assert "signature" in export.download_url
        assert export.download_expires_at == expires_at

    def test_export_has_error_field(self):
        """Export should have error_message field for failed exports."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.FAILED.value,
            error_message="Failed to generate PDF: memory limit exceeded",
        )

        assert export.error_message == "Failed to generate PDF: memory limit exceeded"

    def test_export_has_timing_fields(self):
        """Export should have timing fields."""
        now = datetime.now(UTC)
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.RUNNING.value,
            started_at=now,
        )

        assert export.started_at == now
        assert hasattr(export, "completed_at")
        assert hasattr(export, "created_at")


class TestExportMethods:
    """Tests for Export helper methods."""

    def test_is_queued_status(self):
        """is_queued should return True for queued status."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.QUEUED.value,
        )
        assert export.is_queued is True
        assert export.is_running is False

    def test_is_running_status(self):
        """is_running should return True for running status."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.RUNNING.value,
        )
        assert export.is_running is True
        assert export.is_queued is False

    def test_is_completed_status(self):
        """is_completed should return True for completed status."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.COMPLETED.value,
        )
        assert export.is_completed is True
        assert export.is_failed is False

    def test_is_failed_status(self):
        """is_failed should return True for failed status."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.FAILED.value,
        )
        assert export.is_failed is True
        assert export.is_completed is False

    def test_is_finished_for_completed(self):
        """is_finished should return True for completed status."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.COMPLETED.value,
        )
        assert export.is_finished is True

    def test_is_finished_for_failed(self):
        """is_finished should return True for failed status."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.FAILED.value,
        )
        assert export.is_finished is True

    def test_is_finished_for_running(self):
        """is_finished should return False for running status."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.RUNNING.value,
        )
        assert export.is_finished is False

    def test_has_download_with_url_and_expiry(self):
        """has_download should return True when both URL and expiry are set."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.COMPLETED.value,
            download_url="https://storage.example.com/file.csv",
            download_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert export.has_download is True

    def test_has_download_without_url(self):
        """has_download should return False when URL is missing."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.COMPLETED.value,
            download_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert export.has_download is False

    def test_is_download_expired_when_expired(self):
        """is_download_expired should return True when expiry is past."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.COMPLETED.value,
            download_url="https://storage.example.com/file.csv",
            download_expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert export.is_download_expired is True

    def test_is_download_expired_when_not_expired(self):
        """is_download_expired should return False when expiry is future."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.COMPLETED.value,
            download_url="https://storage.example.com/file.csv",
            download_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert export.is_download_expired is False

    def test_is_download_expired_when_none(self):
        """is_download_expired should return True when expiry is None."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.COMPLETED.value,
        )
        assert export.is_download_expired is True

    def test_file_size_mb(self):
        """file_size_mb should return size in megabytes."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.COMPLETED.value,
            file_size_bytes=2 * 1024 * 1024,  # 2 MB
        )
        assert export.file_size_mb == 2.0

    def test_file_size_mb_when_none(self):
        """file_size_mb should return None when file_size_bytes is None."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.QUEUED.value,
        )
        assert export.file_size_mb is None

    def test_get_param_existing(self):
        """get_param should return param value when it exists."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.QUEUED.value,
            params={"date_from": "2025-01-01"},
        )
        assert export.get_param("date_from") == "2025-01-01"

    def test_get_param_missing(self):
        """get_param should return default when param is missing."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.QUEUED.value,
            params={},
        )
        assert export.get_param("date_from", "default") == "default"

    def test_get_param_when_params_none(self):
        """get_param should return default when params is None."""
        export = Export(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            status=ExportStatus.QUEUED.value,
        )
        assert export.get_param("date_from", "default") == "default"


# =============================================================================
# ExportSchedule Model Tests
# =============================================================================


class TestExportScheduleModel:
    """Tests for the ExportSchedule model."""

    def test_export_schedule_has_required_fields(self):
        """ExportSchedule should have all required fields."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
        )

        assert schedule.format == "csv"
        assert schedule.resource == "issues"
        assert schedule.cron_expression == "0 9 * * MON"

    def test_export_schedule_has_timezone_field(self):
        """ExportSchedule should have timezone field."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            timezone="UTC",
        )

        assert schedule.timezone == "UTC"

    def test_export_schedule_custom_timezone(self):
        """ExportSchedule should accept custom timezone."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            timezone="America/New_York",
        )

        assert schedule.timezone == "America/New_York"

    def test_export_schedule_has_is_enabled_field(self):
        """ExportSchedule should have is_enabled field."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            is_enabled=True,
        )

        assert schedule.is_enabled is True

    def test_export_schedule_can_be_disabled(self):
        """ExportSchedule can be disabled."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            is_enabled=False,
        )

        assert schedule.is_enabled is False

    def test_export_schedule_has_params_field(self):
        """ExportSchedule should have params JSONB field."""
        params = {
            "date_range": "last_7_days",
            "filters": {"severity": "high"},
        }
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            params=params,
        )

        assert schedule.params["date_range"] == "last_7_days"
        assert schedule.params["filters"]["severity"] == "high"

    def test_export_schedule_has_run_timing_fields(self):
        """ExportSchedule should have last_run_at and next_run_at fields."""
        now = datetime.now(UTC)
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            last_run_at=now,
            next_run_at=now + timedelta(days=7),
        )

        assert schedule.last_run_at == now
        assert schedule.next_run_at == now + timedelta(days=7)


class TestExportScheduleMethods:
    """Tests for ExportSchedule helper methods."""

    def test_is_active_when_enabled(self):
        """is_active should return True when schedule is enabled."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            is_enabled=True,
        )
        assert schedule.is_active is True

    def test_is_active_when_disabled(self):
        """is_active should return False when schedule is disabled."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            is_enabled=False,
        )
        assert schedule.is_active is False

    def test_is_due_when_next_run_passed(self):
        """is_due should return True when next_run_at is in the past."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            is_enabled=True,
            next_run_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        assert schedule.is_due is True

    def test_is_due_when_next_run_future(self):
        """is_due should return False when next_run_at is in the future."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            is_enabled=True,
            next_run_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert schedule.is_due is False

    def test_is_due_when_disabled(self):
        """is_due should return False when schedule is disabled."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            is_enabled=False,
            next_run_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        assert schedule.is_due is False

    def test_is_due_when_next_run_none(self):
        """is_due should return False when next_run_at is None."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            is_enabled=True,
        )
        assert schedule.is_due is False

    def test_has_run_when_last_run_set(self):
        """has_run should return True when last_run_at is set."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            last_run_at=datetime.now(UTC),
        )
        assert schedule.has_run is True

    def test_has_run_when_never_run(self):
        """has_run should return False when last_run_at is None."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
        )
        assert schedule.has_run is False

    def test_get_param_existing(self):
        """get_param should return param value when it exists."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            params={"date_range": "last_7_days"},
        )
        assert schedule.get_param("date_range") == "last_7_days"

    def test_get_param_missing(self):
        """get_param should return default when param is missing."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
            params={},
        )
        assert schedule.get_param("date_range", "last_30_days") == "last_30_days"

    def test_get_param_when_params_none(self):
        """get_param should return default when params is None."""
        schedule = ExportSchedule(
            format=ExportFormat.CSV.value,
            resource=ExportResource.ISSUES.value,
            cron_expression="0 9 * * MON",
        )
        assert schedule.get_param("date_range", "last_30_days") == "last_30_days"


# =============================================================================
# Relationship Tests
# =============================================================================


class TestExportRelationships:
    """Tests for model relationships - primarily documentation/design verification."""

    def test_export_has_project_relationship_attr(self):
        """Export should have project relationship attribute."""
        assert hasattr(Export, "project")

    def test_export_schedule_has_project_relationship_attr(self):
        """ExportSchedule should have project relationship attribute."""
        assert hasattr(ExportSchedule, "project")


# =============================================================================
# Table and Column Tests (Design Verification)
# =============================================================================


class TestExportTableDesign:
    """Tests verifying table names and key design decisions."""

    def test_export_table_name(self):
        """Export should use correct table name."""
        assert Export.__tablename__ == "exports"

    def test_export_schedule_table_name(self):
        """ExportSchedule should use correct table name."""
        assert ExportSchedule.__tablename__ == "export_schedules"
