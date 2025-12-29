"""
Tests for CSV export service.
"""

import csv
import io
import uuid
from datetime import UTC, datetime
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


class TestCSVStreamingExport:
    """Tests for streaming CSV export functionality."""

    @pytest.mark.asyncio
    async def test_export_issues_streaming_yields_chunks(
        self,
        mock_db_session: AsyncMock,
        mock_issues: list[MagicMock],
        test_project_id: uuid.UUID,
    ) -> None:
        """Test issues streaming export yields multiple chunks."""
        # Setup mock to return data on first call, empty on second
        mock_result_with_data = MagicMock()
        mock_result_with_data.scalars.return_value.all.return_value = mock_issues

        mock_result_empty = MagicMock()
        mock_result_empty.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_result_with_data, mock_result_empty]

        exporter = CSVExporter()
        chunks = []
        async for chunk in exporter.export_issues_streaming(
            mock_db_session,
            test_project_id,
            batch_size=10,
        ):
            chunks.append(chunk)

        # Should have at least header chunk and data chunk
        assert len(chunks) >= 1

        # First chunk should contain header with BOM
        first_chunk = chunks[0].decode("utf-8")
        assert first_chunk.startswith("\ufeff")
        assert "URL" in first_chunk

    @pytest.mark.asyncio
    async def test_export_issues_streaming_header_only_when_no_data(
        self,
        mock_db_session: AsyncMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test streaming export yields only header when no data exists."""
        mock_result_empty = MagicMock()
        mock_result_empty.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result_empty

        exporter = CSVExporter()
        chunks = []
        async for chunk in exporter.export_issues_streaming(
            mock_db_session,
            test_project_id,
        ):
            chunks.append(chunk)

        # Should have exactly one chunk (header only)
        assert len(chunks) == 1
        header = chunks[0].decode("utf-8")
        assert "URL" in header

    @pytest.mark.asyncio
    async def test_export_backlinks_streaming_yields_chunks(
        self,
        mock_db_session: AsyncMock,
        mock_backlinks: list[MagicMock],
        test_project_id: uuid.UUID,
    ) -> None:
        """Test backlinks streaming export yields chunks."""
        mock_result_with_data = MagicMock()
        mock_result_with_data.scalars.return_value.all.return_value = mock_backlinks

        mock_result_empty = MagicMock()
        mock_result_empty.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_result_with_data, mock_result_empty]

        exporter = CSVExporter()
        chunks = []
        async for chunk in exporter.export_backlinks_streaming(
            mock_db_session,
            test_project_id,
            batch_size=10,
        ):
            chunks.append(chunk)

        assert len(chunks) >= 1
        first_chunk = chunks[0].decode("utf-8")
        assert "Source URL" in first_chunk


class TestCSVEmptyDataHandling:
    """Tests for CSV export with empty data."""

    @pytest.mark.asyncio
    async def test_export_issues_empty_returns_headers_only(
        self,
        mock_db_session: AsyncMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test issues export with no data returns only headers."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        exporter = CSVExporter()
        result = await exporter.export_issues(mock_db_session, test_project_id)

        content = result.decode("utf-8")
        if content.startswith("\ufeff"):
            content = content[1:]

        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Should have only header row
        assert len(rows) == 1
        assert "URL" in rows[0]

    @pytest.mark.asyncio
    async def test_export_backlinks_empty_returns_headers_only(
        self,
        mock_db_session: AsyncMock,
        test_project_id: uuid.UUID,
    ) -> None:
        """Test backlinks export with no data returns only headers."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        exporter = CSVExporter()
        result = await exporter.export_backlinks(mock_db_session, test_project_id)

        content = result.decode("utf-8")
        if content.startswith("\ufeff"):
            content = content[1:]

        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        assert len(rows) == 1
        assert "Source URL" in rows[0]

    @pytest.mark.asyncio
    async def test_export_pages_empty_returns_headers_only(
        self,
        mock_db_session: AsyncMock,
        test_crawl_run_id: uuid.UUID,
    ) -> None:
        """Test pages export with no data returns only headers."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        exporter = CSVExporter()
        result = await exporter.export_pages(mock_db_session, test_crawl_run_id)

        content = result.decode("utf-8")
        if content.startswith("\ufeff"):
            content = content[1:]

        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        assert len(rows) == 1
        assert "URL" in rows[0]


class TestCSVEncodingAndSpecialCharacters:
    """Tests for CSV export encoding and special character handling."""

    def test_utf8_bom_constant(self) -> None:
        """Test UTF-8 BOM constant is correct."""
        assert CSVExporter.UTF8_BOM == "\ufeff"

    def test_special_characters_in_data(self) -> None:
        """Test CSV properly escapes special characters."""
        exporter = CSVExporter(include_bom=False)
        buffer = io.StringIO()
        rows = [
            ["value with, comma", 'value with "quotes"', "normal value"],
            ["line\nbreak", "tab\there", "emoji \U0001f4c8"],
        ]
        exporter._write_rows(buffer, rows)

        content = buffer.getvalue()
        reader = csv.reader(io.StringIO(content))
        read_rows = list(reader)

        # Verify special characters are preserved
        assert read_rows[0][0] == "value with, comma"
        assert read_rows[0][1] == 'value with "quotes"'
        assert read_rows[1][2] == "emoji \U0001f4c8"
