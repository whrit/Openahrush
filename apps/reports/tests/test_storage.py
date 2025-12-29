"""
Tests for MinIO storage service.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from semrush_reports.storage import ExportStorage, MinIOStorage


class TestMinIOStorage:
    """Tests for MinIOStorage class."""

    @patch("semrush_reports.storage.Minio")
    @patch("semrush_reports.storage.get_settings")
    def test_init_creates_client(
        self,
        mock_get_settings: MagicMock,
        mock_minio_class: MagicMock,
    ) -> None:
        """Test MinIOStorage initializes Minio client."""
        mock_settings = MagicMock()
        mock_settings.minio_endpoint = "localhost:9000"
        mock_settings.minio_access_key.get_secret_value.return_value = "access"
        mock_settings.minio_secret_key.get_secret_value.return_value = "secret"
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.minio_secure = False
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        MinIOStorage()  # Instantiate to test initialization

        mock_minio_class.assert_called_once_with(
            "localhost:9000",
            access_key="access",
            secret_key="secret",
            secure=False,
        )

    @patch("semrush_reports.storage.Minio")
    @patch("semrush_reports.storage.get_settings")
    def test_ensure_bucket_creates_if_missing(
        self,
        mock_get_settings: MagicMock,
        mock_minio_class: MagicMock,
    ) -> None:
        """Test _ensure_bucket creates bucket if it doesn't exist."""
        mock_settings = MagicMock()
        mock_settings.minio_endpoint = "localhost:9000"
        mock_settings.minio_access_key.get_secret_value.return_value = "access"
        mock_settings.minio_secret_key.get_secret_value.return_value = "secret"
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.minio_secure = False
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        mock_minio_class.return_value = mock_client

        MinIOStorage()  # Instantiate to trigger bucket creation

        mock_client.make_bucket.assert_called_once_with("test-bucket")

    @patch("semrush_reports.storage.Minio")
    @patch("semrush_reports.storage.get_settings")
    def test_upload(
        self,
        mock_get_settings: MagicMock,
        mock_minio_class: MagicMock,
    ) -> None:
        """Test file upload."""
        mock_settings = MagicMock()
        mock_settings.minio_endpoint = "localhost:9000"
        mock_settings.minio_access_key.get_secret_value.return_value = "access"
        mock_settings.minio_secret_key.get_secret_value.return_value = "secret"
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.minio_secure = False
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        storage = MinIOStorage()
        result = storage.upload("test/key.csv", b"test data", "text/csv")

        assert result == "s3://test-bucket/test/key.csv"
        mock_client.put_object.assert_called_once()

    @patch("semrush_reports.storage.Minio")
    @patch("semrush_reports.storage.get_settings")
    def test_presigned_url(
        self,
        mock_get_settings: MagicMock,
        mock_minio_class: MagicMock,
    ) -> None:
        """Test presigned URL generation."""
        mock_settings = MagicMock()
        mock_settings.minio_endpoint = "localhost:9000"
        mock_settings.minio_access_key.get_secret_value.return_value = "access"
        mock_settings.minio_secret_key.get_secret_value.return_value = "secret"
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.minio_secure = False
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_client.presigned_get_object.return_value = "https://presigned.url"
        mock_minio_class.return_value = mock_client

        storage = MinIOStorage()
        result = storage.presigned_url("test/key.csv", expires_hours=24)

        assert result == "https://presigned.url"
        mock_client.presigned_get_object.assert_called_once()

    @patch("semrush_reports.storage.Minio")
    @patch("semrush_reports.storage.get_settings")
    def test_delete(
        self,
        mock_get_settings: MagicMock,
        mock_minio_class: MagicMock,
    ) -> None:
        """Test file deletion."""
        mock_settings = MagicMock()
        mock_settings.minio_endpoint = "localhost:9000"
        mock_settings.minio_access_key.get_secret_value.return_value = "access"
        mock_settings.minio_secret_key.get_secret_value.return_value = "secret"
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.minio_secure = False
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio_class.return_value = mock_client

        storage = MinIOStorage()
        storage.delete("test/key.csv")

        mock_client.remove_object.assert_called_once_with("test-bucket", "test/key.csv")

    @patch("semrush_reports.storage.Minio")
    @patch("semrush_reports.storage.get_settings")
    def test_exists_true(
        self,
        mock_get_settings: MagicMock,
        mock_minio_class: MagicMock,
    ) -> None:
        """Test file exists check - file exists."""
        mock_settings = MagicMock()
        mock_settings.minio_endpoint = "localhost:9000"
        mock_settings.minio_access_key.get_secret_value.return_value = "access"
        mock_settings.minio_secret_key.get_secret_value.return_value = "secret"
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.minio_secure = False
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_client.stat_object.return_value = MagicMock()
        mock_minio_class.return_value = mock_client

        storage = MinIOStorage()
        assert storage.exists("test/key.csv") is True

    @patch("semrush_reports.storage.Minio")
    @patch("semrush_reports.storage.get_settings")
    def test_exists_false(
        self,
        mock_get_settings: MagicMock,
        mock_minio_class: MagicMock,
    ) -> None:
        """Test file exists check - file does not exist."""
        from minio.error import S3Error

        mock_settings = MagicMock()
        mock_settings.minio_endpoint = "localhost:9000"
        mock_settings.minio_access_key.get_secret_value.return_value = "access"
        mock_settings.minio_secret_key.get_secret_value.return_value = "secret"
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.minio_secure = False
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_client.stat_object.side_effect = S3Error("NoSuchKey", "NoSuchKey", "", "", "", "")
        mock_minio_class.return_value = mock_client

        storage = MinIOStorage()
        assert storage.exists("test/key.csv") is False


class TestExportStorage:
    """Tests for ExportStorage class."""

    def test_get_export_key(self, mock_storage: MagicMock) -> None:
        """Test export key generation."""
        storage = ExportStorage(storage=mock_storage)

        project_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        export_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

        key = storage.get_export_key(project_id, export_id, "csv")

        assert key == f"exports/{project_id}/{export_id}.csv"

    def test_get_content_type_csv(self, mock_storage: MagicMock) -> None:
        """Test content type for CSV."""
        storage = ExportStorage(storage=mock_storage)
        assert storage.get_content_type("csv") == "text/csv; charset=utf-8"

    def test_get_content_type_json(self, mock_storage: MagicMock) -> None:
        """Test content type for JSON."""
        storage = ExportStorage(storage=mock_storage)
        assert storage.get_content_type("json") == "application/json; charset=utf-8"

    def test_get_content_type_pdf(self, mock_storage: MagicMock) -> None:
        """Test content type for PDF."""
        storage = ExportStorage(storage=mock_storage)
        assert storage.get_content_type("pdf") == "application/pdf"

    def test_get_content_type_unknown(self, mock_storage: MagicMock) -> None:
        """Test content type for unknown format."""
        storage = ExportStorage(storage=mock_storage)
        assert storage.get_content_type("unknown") == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_store_export(self, mock_storage: MagicMock) -> None:
        """Test storing an export."""
        mock_storage.presigned_url.return_value = "https://download.url"

        storage = ExportStorage(storage=mock_storage)

        project_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        export_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        data = b"test export data"

        key, size, url = await storage.store_export(project_id, export_id, "csv", data)

        assert key == f"exports/{project_id}/{export_id}.csv"
        assert size == len(data)
        assert url == "https://download.url"

        mock_storage.upload.assert_called_once()
        mock_storage.presigned_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_download_url(self, mock_storage: MagicMock) -> None:
        """Test refreshing download URL."""
        mock_storage.presigned_url.return_value = "https://new.url"

        storage = ExportStorage(storage=mock_storage)
        url = await storage.refresh_download_url("test/key.csv", expires_hours=24)

        assert url == "https://new.url"
        mock_storage.presigned_url.assert_called_once_with("test/key.csv", 24)

    @pytest.mark.asyncio
    async def test_delete_export(self, mock_storage: MagicMock) -> None:
        """Test deleting an export."""
        storage = ExportStorage(storage=mock_storage)
        await storage.delete_export("test/key.csv")

        mock_storage.delete.assert_called_once_with("test/key.csv")
