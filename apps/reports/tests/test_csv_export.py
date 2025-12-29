"""
Tests for CSV export service.
"""

import csv
import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from semrush_reports.csv_export import CSVExporter, format_datetime, format_list


class TestCSVExporter:
    """Tests for CSVExporter class."""

    def test_init_with_bom(self) -> None:
        """Test CSVExporter initializes with BOM by default."""
        exporter = CSVExporter()
        assert exporter.include_bom is True

    def test_init_without_bom(self) -> None:
        """Test CSVExporter can be initialized without BOM."""
        exporter = CSVExporter(include_bom=False)
        assert exporter.include_bom is False

    def test_write_header_with_bom(self) -> None:
        """Test header is written with UTF-8 BOM."""
        exporter = CSVExporter(include_bom=True)
        buffer = io.StringIO()
        exporter._write_header(buffer, ["Col1", "Col2", "Col3"])

        content = buffer.getvalue()
        assert content.startswith("\ufeff")
        assert "Col1,Col2,Col3" in content

    def test_write_header_without_bom(self) -> None:
        """Test header is written without BOM when disabled."""
        exporter = CSVExporter(include_bom=False)
        buffer = io.StringIO()
        exporter._write_header(buffer, ["Col1", "Col2", "Col3"])

        content = buffer.getvalue()
        assert not content.startswith("\ufeff")
        assert content.startswith("Col1,Col2,Col3")

    def test_write_rows(self) -> None:
        """Test data rows are written correctly."""
        exporter = CSVExporter()
        buffer = io.StringIO()
        rows = [
            ["value1", "value2", "value3"],
            ["value4", "value5", "value6"],
        ]
        exporter._write_rows(buffer, rows)

        content = buffer.getvalue()
        reader = csv.reader(io.StringIO(content))
        read_rows = list(reader)

        assert len(read_rows) == 2
        assert read_rows[0] == ["value1", "value2", "value3"]
        assert read_rows[1] == ["value4", "value5", "value6"]

    @pytest.mark.asyncio
    async def test_export_issues(
        self,
        mock_db_session: AsyncMock,
        mock_issues: list[MagicMock],
        test_project_id: uuid.UUID,
    ) -> None:
        """Test issues CSV export."""
        # Setup mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_issues
        mock_db_session.execute.return_value = mock_result

        exporter = CSVExporter()
        result = await exporter.export_issues(
            mock_db_session,
            test_project_id,
        )

        # Verify result is bytes
        assert isinstance(result, bytes)

        # Parse CSV
        content = result.decode("utf-8")
        # Skip BOM
        if content.startswith("\ufeff"):
            content = content[1:]

        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Verify header
        assert rows[0] == [
            "URL",
            "Issue Type",
            "Category",
            "Severity",
            "Impact Score",
            "Confidence",
            "Evidence",
        ]

        # Verify data rows
        assert len(rows) == 6  # Header + 5 issues

    @pytest.mark.asyncio
    async def test_export_backlinks(
        self,
        mock_db_session: AsyncMock,
        mock_backlinks: list[MagicMock],
        test_project_id: uuid.UUID,
    ) -> None:
        """Test backlinks CSV export."""
        # Setup mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_backlinks
        mock_db_session.execute.return_value = mock_result

        exporter = CSVExporter()
        result = await exporter.export_backlinks(
            mock_db_session,
            test_project_id,
        )

        # Verify result is bytes
        assert isinstance(result, bytes)

        # Parse CSV
        content = result.decode("utf-8")
        if content.startswith("\ufeff"):
            content = content[1:]

        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Verify header
        assert rows[0] == [
            "Source URL",
            "Source Domain",
            "Target URL",
            "Target Domain",
            "Anchor Text",
            "Rel Flags",
            "Source Type",
            "Discovered At",
        ]

        # Verify data rows
        assert len(rows) == 6  # Header + 5 backlinks

    @pytest.mark.asyncio
    async def test_export_pages(
        self,
        mock_db_session: AsyncMock,
        mock_crawl_pages: list[MagicMock],
        test_crawl_run_id: uuid.UUID,
    ) -> None:
        """Test crawl pages CSV export."""
        # Setup mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_crawl_pages
        mock_db_session.execute.return_value = mock_result

        exporter = CSVExporter()
        result = await exporter.export_pages(
            mock_db_session,
            test_crawl_run_id,
        )

        # Verify result is bytes
        assert isinstance(result, bytes)

        # Parse CSV
        content = result.decode("utf-8")
        if content.startswith("\ufeff"):
            content = content[1:]

        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Verify header contains expected columns
        assert "URL" in rows[0]
        assert "Status Code" in rows[0]
        assert "Title" in rows[0]

        # Verify data rows
        assert len(rows) == 6  # Header + 5 pages


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_format_datetime_with_value(self) -> None:
        """Test datetime formatting with valid datetime."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = format_datetime(dt)
        assert "2024-01-15" in result
        assert "10:30:00" in result

    def test_format_datetime_with_none(self) -> None:
        """Test datetime formatting with None."""
        result = format_datetime(None)
        assert result == ""

    def test_format_list_with_values(self) -> None:
        """Test list formatting with values."""
        result = format_list(["a", "b", "c"])
        assert result == "a,b,c"

    def test_format_list_with_none(self) -> None:
        """Test list formatting with None."""
        result = format_list(None)
        assert result == ""

    def test_format_list_empty(self) -> None:
        """Test list formatting with empty list."""
        result = format_list([])
        assert result == ""
