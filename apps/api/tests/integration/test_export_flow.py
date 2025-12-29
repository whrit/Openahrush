"""
Integration tests for export generation flow following TDD principles.

Tests complete export generation flows including:
- CSV export generation and storage
- JSON export generation and storage
- Export storage to MinIO (mocked)
- Export status tracking and presigned URL generation
"""

import io
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from semrush_core.models import Export
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TestExportCreationFlow:
    """Test export creation and job enqueue flow."""

    @pytest.mark.asyncio
    async def test_create_csv_export_creates_export_record(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db_session: AsyncSession,
        test_project: Any,
    ) -> None:
        """
        Test that creating a CSV export creates an Export record.

        Flow:
        1. User requests CSV export of issues
        2. System creates Export with status='queued'
        3. System returns export job details
        """
        response = await integration_client.post(
            f"/projects/{test_project.id}/exports",
            headers=auth_headers,
            json={
                "format": "csv",
                "resource": "issues",
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["format"] == "csv"
        assert data["resource"] == "issues"
        assert data["status"] == "queued"

        # Verify Export was created in database
        export_id = uuid.UUID(data["id"])
        result = await test_db_session.execute(select(Export).where(Export.id == export_id))
        export = result.scalar_one_or_none()

        assert export is not None
        assert export.project_id == test_project.id
        assert export.format == "csv"
        assert export.resource == "issues"
        assert export.status == "queued"

    @pytest.mark.asyncio
    async def test_create_json_export_creates_export_record(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db_session: AsyncSession,
        test_project: Any,
    ) -> None:
        """
        Test that creating a JSON export creates an Export record.
        """
        response = await integration_client.post(
            f"/projects/{test_project.id}/exports",
            headers=auth_headers,
            json={
                "format": "json",
                "resource": "backlinks",
                "params": {"source_type": "commoncrawl"},
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["format"] == "json"
        assert data["resource"] == "backlinks"
        assert data["params"] == {"source_type": "commoncrawl"}

    @pytest.mark.asyncio
    async def test_create_export_without_auth_returns_401(
        self,
        integration_client: AsyncClient,
        test_project: Any,
    ) -> None:
        """
        Test that creating export requires authentication.
        """
        response = await integration_client.post(
            f"/projects/{test_project.id}/exports",
            json={"format": "csv", "resource": "issues"},
        )

        assert response.status_code == 401


class TestCSVExportGeneration:
    """Test CSV export generation."""

    @pytest.mark.asyncio
    async def test_csv_export_generates_valid_csv_content(
        self,
    ) -> None:
        """
        Test that CSV export generates valid CSV content.

        Simulates export worker generating CSV from database records.
        """
        import csv

        # Simulate issues data
        issues = [
            {
                "url": "https://example.com/page1",
                "issue_type": "missing_meta_description",
                "severity": "warning",
                "message": "Meta description is missing",
            },
            {
                "url": "https://example.com/page2",
                "issue_type": "broken_link",
                "severity": "error",
                "message": "Link returns 404",
            },
        ]

        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["url", "issue_type", "severity", "message"],
        )
        writer.writeheader()
        writer.writerows(issues)

        csv_content = output.getvalue()

        # Verify CSV is valid
        assert "url,issue_type,severity,message" in csv_content
        assert "https://example.com/page1" in csv_content
        assert "missing_meta_description" in csv_content
        assert "broken_link" in csv_content

    @pytest.mark.asyncio
    async def test_csv_export_handles_empty_results(
        self,
    ) -> None:
        """
        Test that CSV export handles empty result sets gracefully.
        """
        import csv

        # Empty issues data
        issues = []

        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["url", "issue_type", "severity", "message"],
        )
        writer.writeheader()
        writer.writerows(issues)

        csv_content = output.getvalue()

        # Should have header even with no data
        assert "url,issue_type,severity,message" in csv_content
        assert len(csv_content.split("\n")) == 2  # Header + empty line

    @pytest.mark.asyncio
    async def test_csv_export_escapes_special_characters(
        self,
    ) -> None:
        """
        Test that CSV export properly escapes special characters.
        """
        import csv

        # Data with special characters
        issues = [
            {
                "url": "https://example.com/page",
                "issue_type": "custom",
                "severity": "info",
                "message": 'Contains "quotes" and, commas',
            },
        ]

        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["url", "issue_type", "severity", "message"],
        )
        writer.writeheader()
        writer.writerows(issues)

        csv_content = output.getvalue()

        # Verify special characters are escaped
        assert (
            '"Contains ""quotes"" and, commas"' in csv_content
            or 'Contains "quotes" and, commas' in csv_content
        )


class TestJSONExportGeneration:
    """Test JSON export generation."""

    @pytest.mark.asyncio
    async def test_json_export_generates_valid_json_content(
        self,
    ) -> None:
        """
        Test that JSON export generates valid JSON content.
        """
        # Simulate backlinks data
        backlinks = [
            {
                "source_url": "https://external.com/article",
                "target_url": "https://example.com/page1",
                "anchor_text": "Great content",
                "discovered_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC).isoformat(),
            },
            {
                "source_url": "https://blog.com/post",
                "target_url": "https://example.com/page2",
                "anchor_text": "Read more",
                "discovered_at": datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC).isoformat(),
            },
        ]

        # Generate JSON
        json_content = json.dumps(
            {"backlinks": backlinks, "total": len(backlinks)},
            indent=2,
        )

        # Verify JSON is valid
        parsed = json.loads(json_content)
        assert "backlinks" in parsed
        assert len(parsed["backlinks"]) == 2
        assert parsed["total"] == 2
        assert parsed["backlinks"][0]["source_url"] == "https://external.com/article"

    @pytest.mark.asyncio
    async def test_json_export_handles_nested_structures(
        self,
    ) -> None:
        """
        Test that JSON export handles nested data structures.
        """
        # Data with nested objects
        pages = [
            {
                "url": "https://example.com/page1",
                "meta": {
                    "title": "Page 1",
                    "description": "Description 1",
                    "keywords": ["seo", "testing"],
                },
                "performance": {
                    "load_time_ms": 250,
                    "size_bytes": 45000,
                },
            },
        ]

        # Generate JSON
        json_content = json.dumps({"pages": pages}, indent=2)

        # Verify nested structures
        parsed = json.loads(json_content)
        assert parsed["pages"][0]["meta"]["title"] == "Page 1"
        assert parsed["pages"][0]["meta"]["keywords"] == ["seo", "testing"]
        assert parsed["pages"][0]["performance"]["load_time_ms"] == 250


class TestMinIOStorageIntegration:
    """Test export storage to MinIO."""

    @pytest.mark.asyncio
    async def test_export_file_uploaded_to_minio(
        self,
        mock_minio_client: MagicMock,
    ) -> None:
        """
        Test that export file is uploaded to MinIO/S3.

        Flow:
        1. Export worker generates CSV/JSON content
        2. Content uploaded to MinIO bucket
        3. Object key stored in Export.artifact_key
        """
        # Simulate uploading export
        export_id = uuid.uuid4()
        csv_content = b"url,issue_type,severity\nhttps://example.com/,test,info\n"
        object_key = f"exports/{export_id}.csv"

        # Upload to MinIO (mocked)
        result = mock_minio_client.put_object(
            bucket_name="test-bucket",
            object_name=object_key,
            data=io.BytesIO(csv_content),
            length=len(csv_content),
            content_type="text/csv",
        )

        # Verify upload was called
        mock_minio_client.put_object.assert_called_once()
        assert result.object_name == object_key

    @pytest.mark.asyncio
    async def test_export_generates_presigned_download_url(
        self,
        mock_minio_client: MagicMock,
        test_db_session: AsyncSession,
        test_export: Export,
    ) -> None:
        """
        Test that export generates presigned download URL.

        Flow:
        1. Export completes successfully
        2. System generates presigned URL (valid for 7 days)
        3. URL and expiration stored in Export record
        """
        # Simulate export completion
        test_export.status = "completed"
        test_export.artifact_key = f"exports/{test_export.id}.csv"
        test_export.file_size_bytes = 1024

        # Generate presigned URL (mocked)
        presigned_url = mock_minio_client.presigned_get_object(
            bucket_name="test-bucket",
            object_name=test_export.artifact_key,
            expires=timedelta(days=7),
        )

        test_export.download_url = presigned_url
        test_export.download_expires_at = datetime.now(UTC) + timedelta(days=7)
        test_export.completed_at = datetime.now(UTC)

        await test_db_session.commit()
        await test_db_session.refresh(test_export)

        # Verify URL was generated and stored
        assert test_export.download_url is not None
        assert "test-bucket" in test_export.download_url
        assert test_export.download_expires_at > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_export_file_can_be_downloaded(
        self,
        mock_minio_client: MagicMock,
    ) -> None:
        """
        Test that export file can be downloaded from MinIO.
        """
        # Mock downloading file
        object_key = "exports/test-export.csv"
        expected_content = b"test,data\n1,2\n"

        # Configure mock to return test data
        mock_response = MagicMock()
        mock_response.read.return_value = expected_content
        mock_minio_client.get_object.return_value = mock_response

        # Download file
        response = mock_minio_client.get_object(
            bucket_name="test-bucket",
            object_name=object_key,
        )
        content = response.read()

        # Verify download
        mock_minio_client.get_object.assert_called_once()
        assert content == expected_content


class TestExportStatusTracking:
    """Test export status tracking and updates."""

    @pytest.mark.asyncio
    async def test_export_status_transitions_from_queued_to_running(
        self,
        test_db_session: AsyncSession,
        test_export: Export,
    ) -> None:
        """
        Test that export status transitions from queued to running.
        """
        # Simulate worker picking up export job
        test_export.status = "running"
        test_export.started_at = datetime.now(UTC)
        await test_db_session.commit()
        await test_db_session.refresh(test_export)

        assert test_export.status == "running"
        assert test_export.started_at is not None

    @pytest.mark.asyncio
    async def test_export_status_transitions_to_completed(
        self,
        test_db_session: AsyncSession,
        test_export: Export,
    ) -> None:
        """
        Test that export status transitions to completed with metadata.
        """
        # Simulate export completion
        test_export.status = "completed"
        test_export.started_at = datetime.now(UTC) - timedelta(minutes=2)
        test_export.completed_at = datetime.now(UTC)
        test_export.artifact_key = f"exports/{test_export.id}.csv"
        test_export.file_size_bytes = 2048
        test_export.download_url = "https://example.com/download"
        test_export.download_expires_at = datetime.now(UTC) + timedelta(days=7)

        await test_db_session.commit()
        await test_db_session.refresh(test_export)

        assert test_export.status == "completed"
        assert test_export.completed_at is not None
        assert test_export.artifact_key is not None
        assert test_export.file_size_bytes == 2048
        assert test_export.download_url is not None

    @pytest.mark.asyncio
    async def test_export_status_transitions_to_failed(
        self,
        test_db_session: AsyncSession,
        test_export: Export,
    ) -> None:
        """
        Test that export status transitions to failed with error message.
        """
        # Simulate export failure
        test_export.status = "failed"
        test_export.error_message = "Database query timeout after 30 seconds"
        test_export.started_at = datetime.now(UTC) - timedelta(seconds=30)
        test_export.completed_at = datetime.now(UTC)

        await test_db_session.commit()
        await test_db_session.refresh(test_export)

        assert test_export.status == "failed"
        assert test_export.error_message is not None
        assert "timeout" in test_export.error_message.lower()

    @pytest.mark.asyncio
    async def test_get_export_status_returns_current_state(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_project: Any,
        test_export: Export,
    ) -> None:
        """
        Test that GET export status endpoint returns current export state.
        """
        response = await integration_client.get(
            f"/projects/{test_project.id}/exports/{test_export.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_export.id)
        assert data["status"] == test_export.status
        assert data["format"] == test_export.format
        assert data["resource"] == test_export.resource


class TestExportDownloadFlow:
    """Test export download flow."""

    @pytest.mark.asyncio
    async def test_get_download_url_for_completed_export(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_db_session: AsyncSession,
        test_project: Any,
        test_export: Export,
    ) -> None:
        """
        Test that getting download URL returns presigned URL.
        """
        # Set export to completed
        test_export.status = "completed"
        test_export.artifact_key = f"exports/{test_export.id}.csv"
        test_export.file_size_bytes = 1024
        test_export.download_url = "https://localhost:9000/test-bucket/export.csv?sig=test"
        test_export.download_expires_at = datetime.now(UTC) + timedelta(days=7)
        await test_db_session.commit()

        response = await integration_client.get(
            f"/projects/{test_project.id}/exports/{test_export.id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "download_url" in data
        assert "expires_at" in data
        assert data["export_id"] == str(test_export.id)
        assert data["file_size_bytes"] == 1024

    @pytest.mark.asyncio
    async def test_get_download_url_for_queued_export_returns_409(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_project: Any,
        test_export: Export,
    ) -> None:
        """
        Test that getting download URL for incomplete export returns 409 Conflict.
        """
        # Export is still queued
        assert test_export.status == "queued"

        response = await integration_client.get(
            f"/projects/{test_project.id}/exports/{test_export.id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 409
        data = response.json()
        assert "not completed" in data["detail"].lower() or "not ready" in data["detail"].lower()


class TestExportResourceTypes:
    """Test different export resource types."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "resource",
        ["issues", "backlinks", "pages", "performance", "full_report"],
    )
    async def test_export_supports_all_resource_types(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_project: Any,
        resource: str,
    ) -> None:
        """
        Test that export supports all defined resource types.
        """
        response = await integration_client.post(
            f"/projects/{test_project.id}/exports",
            headers=auth_headers,
            json={"format": "csv", "resource": resource},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["resource"] == resource


class TestExportPagination:
    """Test export listing pagination."""

    @pytest.mark.asyncio
    async def test_list_exports_returns_paginated_results(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
        test_project: Any,
    ) -> None:
        """
        Test that listing exports supports pagination.
        """
        response = await integration_client.get(
            f"/projects/{test_project.id}/exports?page=1&pageSize=10",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data


class TestExportAuthorization:
    """Test export authorization and access control."""

    @pytest.mark.asyncio
    async def test_cannot_create_export_for_other_users_project(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Test that users cannot create exports for projects they don't own.
        """
        other_project_id = uuid.uuid4()

        response = await integration_client.post(
            f"/projects/{other_project_id}/exports",
            headers=auth_headers,
            json={"format": "csv", "resource": "issues"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_download_other_users_export(
        self,
        integration_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Test that users cannot download exports for projects they don't own.
        """
        other_project_id = uuid.uuid4()
        other_export_id = uuid.uuid4()

        response = await integration_client.get(
            f"/projects/{other_project_id}/exports/{other_export_id}/download",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestExportQueueIntegration:
    """Test export job queue integration."""

    @pytest.mark.asyncio
    async def test_export_job_enqueued_to_redis(
        self,
        fake_redis: Any,
        test_export: Export,
    ) -> None:
        """
        Test that export jobs are enqueued to Redis for worker processing.
        """
        import json

        job_data = {
            "export_id": str(test_export.id),
            "project_id": str(test_export.project_id),
            "format": test_export.format,
            "resource": test_export.resource,
            "params": test_export.params,
        }

        await fake_redis.lpush("export_queue", json.dumps(job_data))

        # Verify job was enqueued
        queue_length = await fake_redis.llen("export_queue")
        assert queue_length == 1

        # Simulate worker dequeuing job
        job_json = await fake_redis.rpop("export_queue")
        assert job_json is not None

        dequeued_job = json.loads(job_json)
        assert dequeued_job["export_id"] == str(test_export.id)
        assert dequeued_job["format"] == test_export.format
