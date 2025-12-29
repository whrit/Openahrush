"""
Tests for JSON export service.
"""

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from semrush_reports.json_export import JSONEncoder, JSONExporter


class TestJSONEncoder:
    """Tests for custom JSON encoder."""

    def test_encode_datetime(self) -> None:
        """Test datetime encoding."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = json.dumps({"date": dt}, cls=JSONEncoder)
        data = json.loads(result)
        assert "2024-01-15" in data["date"]

    def test_encode_uuid(self) -> None:
        """Test UUID encoding."""
        uid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = json.dumps({"id": uid}, cls=JSONEncoder)
        data = json.loads(result)
        assert data["id"] == "12345678-1234-5678-1234-567812345678"

    def test_encode_decimal(self) -> None:
        """Test Decimal encoding."""
        dec = Decimal("123.45")
        result = json.dumps({"value": dec}, cls=JSONEncoder)
        data = json.loads(result)
        assert data["value"] == 123.45

    def test_encode_object_with_to_dict(self) -> None:
        """Test object with to_dict method."""
        obj = MagicMock()
        obj.to_dict.return_value = {"key": "value"}
        result = json.dumps({"obj": obj}, cls=JSONEncoder)
        data = json.loads(result)
        assert data["obj"] == {"key": "value"}


class TestJSONExporter:
    """Tests for JSONExporter class."""

    def test_init_default(self) -> None:
        """Test JSONExporter initializes with default settings."""
        exporter = JSONExporter()
        assert exporter.pretty is False
        assert exporter.indent is None

    def test_init_pretty(self) -> None:
        """Test JSONExporter with pretty printing."""
        exporter = JSONExporter(pretty=True)
        assert exporter.pretty is True
        assert exporter.indent == 2

    def test_dumps_compact(self) -> None:
        """Test compact JSON serialization."""
        exporter = JSONExporter(pretty=False)
        result = exporter._dumps({"key": "value"})
        assert "\n" not in result
        assert json.loads(result) == {"key": "value"}

    def test_dumps_pretty(self) -> None:
        """Test pretty JSON serialization."""
        exporter = JSONExporter(pretty=True)
        result = exporter._dumps({"key": "value"})
        assert "\n" in result
        assert json.loads(result) == {"key": "value"}

    @pytest.mark.asyncio
    async def test_export_issues(
        self,
        mock_db_session: AsyncMock,
        mock_issues: list[MagicMock],
        test_project_id: uuid.UUID,
    ) -> None:
        """Test issues JSON export."""
        # Setup mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_issues
        mock_db_session.execute.return_value = mock_result

        exporter = JSONExporter()
        result = await exporter.export_issues(
            mock_db_session,
            test_project_id,
        )

        # Verify result is bytes
        assert isinstance(result, bytes)

        # Parse JSON
        data = json.loads(result.decode("utf-8"))

        # Verify structure
        assert data["export_type"] == "issues"
        assert data["project_id"] == str(test_project_id)
        assert "exported_at" in data
        assert "total_count" in data
        assert "items" in data
        assert len(data["items"]) == 5

    @pytest.mark.asyncio
    async def test_export_backlinks(
        self,
        mock_db_session: AsyncMock,
        mock_backlinks: list[MagicMock],
        test_project_id: uuid.UUID,
    ) -> None:
        """Test backlinks JSON export."""
        # Setup mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_backlinks
        mock_db_session.execute.return_value = mock_result

        exporter = JSONExporter()
        result = await exporter.export_backlinks(
            mock_db_session,
            test_project_id,
        )

        # Verify result is bytes
        assert isinstance(result, bytes)

        # Parse JSON
        data = json.loads(result.decode("utf-8"))

        # Verify structure
        assert data["export_type"] == "backlinks"
        assert data["project_id"] == str(test_project_id)
        assert len(data["items"]) == 5

        # Verify item structure
        item = data["items"][0]
        assert "source_url" in item
        assert "source_domain" in item
        assert "target_url" in item
        assert "anchor" in item

    @pytest.mark.asyncio
    async def test_export_pages(
        self,
        mock_db_session: AsyncMock,
        mock_crawl_pages: list[MagicMock],
        test_crawl_run_id: uuid.UUID,
    ) -> None:
        """Test pages JSON export."""
        # Setup mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_crawl_pages
        mock_db_session.execute.return_value = mock_result

        exporter = JSONExporter()
        result = await exporter.export_pages(
            mock_db_session,
            test_crawl_run_id,
        )

        # Verify result is bytes
        assert isinstance(result, bytes)

        # Parse JSON
        data = json.loads(result.decode("utf-8"))

        # Verify structure
        assert data["export_type"] == "pages"
        assert data["crawl_run_id"] == str(test_crawl_run_id)
        assert len(data["items"]) == 5

        # Verify item structure
        item = data["items"][0]
        assert "url" in item
        assert "status_code" in item
        assert "title" in item

    @pytest.mark.asyncio
    async def test_export_issues_jsonl(
        self,
        mock_db_session: AsyncMock,
        mock_issues: list[MagicMock],
        test_project_id: uuid.UUID,
    ) -> None:
        """Test issues JSON Lines streaming export."""
        # Setup mock query result - return all issues on first call, empty on second
        mock_result_with_data = MagicMock()
        mock_result_with_data.scalars.return_value.all.return_value = mock_issues

        mock_result_empty = MagicMock()
        mock_result_empty.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_result_with_data, mock_result_empty]

        exporter = JSONExporter()
        chunks = []
        async for chunk in exporter.export_issues_jsonl(
            mock_db_session,
            test_project_id,
            batch_size=10,
        ):
            chunks.append(chunk)

        # Verify we got chunks
        assert len(chunks) > 0

        # Verify each line is valid JSON
        content = b"".join(chunks).decode("utf-8")
        lines = [line for line in content.strip().split("\n") if line]

        for line in lines:
            data = json.loads(line)
            assert "url" in data
            assert "issue_type_id" in data
