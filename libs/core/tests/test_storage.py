"""
Tests for MinIO storage utilities.

Following TDD: These tests are written FIRST, then the implementation.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from semrush_core.storage.minio import MinIOStorage


class TestMinIOStorageInit:
    """Tests for MinIOStorage initialization."""

    def test_init_creates_minio_client(self):
        """MinIOStorage should create a Minio client with correct parameters."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
                secure=False,
            )

            mock_minio_class.assert_called_once_with(
                "localhost:9000", "minioadmin", "minioadmin", secure=False
            )
            assert storage.bucket == "test-bucket"

    def test_init_with_secure_connection(self):
        """MinIOStorage should support secure (HTTPS) connections."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client

            MinIOStorage(
                endpoint="minio.example.com",
                access_key="key",
                secret_key="secret",
                bucket="secure-bucket",
                secure=True,
            )

            mock_minio_class.assert_called_once_with(
                "minio.example.com", "key", "secret", secure=True
            )


class TestMinIOStorageBucketEnsure:
    """Tests for bucket creation on initialization."""

    def test_ensure_bucket_creates_if_not_exists(self):
        """MinIOStorage should create the bucket if it doesn't exist."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = False
            mock_minio_class.return_value = mock_client

            MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="new-bucket",
            )

            mock_client.bucket_exists.assert_called_once_with("new-bucket")
            mock_client.make_bucket.assert_called_once_with("new-bucket")

    def test_ensure_bucket_skips_if_exists(self):
        """MinIOStorage should not create bucket if it already exists."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client

            MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="existing-bucket",
            )

            mock_client.bucket_exists.assert_called_once_with("existing-bucket")
            mock_client.make_bucket.assert_not_called()


class TestMinIOStorageUpload:
    """Tests for file upload functionality."""

    def test_upload_calls_put_object(self):
        """Upload should call put_object with correct parameters."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            data = b"Hello, World!"
            storage.upload(key="test/file.txt", data=data, content_type="text/plain")

            mock_client.put_object.assert_called_once()
            call_args = mock_client.put_object.call_args
            assert call_args[0][0] == "test-bucket"
            assert call_args[0][1] == "test/file.txt"
            # Third argument should be a file-like object
            assert call_args[0][3] == len(data)
            assert call_args[1]["content_type"] == "text/plain"

    def test_upload_returns_s3_uri(self):
        """Upload should return the S3 URI of the uploaded object."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="my-bucket",
            )

            result = storage.upload(
                key="path/to/file.json", data=b"{}", content_type="application/json"
            )

            assert result == "s3://my-bucket/path/to/file.json"

    def test_upload_handles_binary_data(self):
        """Upload should handle binary data correctly."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            binary_data = bytes(range(256))
            storage.upload(
                key="binary/file.bin",
                data=binary_data,
                content_type="application/octet-stream",
            )

            call_args = mock_client.put_object.call_args
            assert call_args[0][3] == 256

    def test_upload_handles_empty_data(self):
        """Upload should handle empty data."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            result = storage.upload(key="empty.txt", data=b"", content_type="text/plain")

            call_args = mock_client.put_object.call_args
            assert call_args[0][3] == 0
            assert result == "s3://test-bucket/empty.txt"


class TestMinIOStoragePresignedUrl:
    """Tests for presigned URL generation."""

    def test_presigned_url_calls_client_method(self):
        """presigned_url should call presigned_get_object."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_client.presigned_get_object.return_value = (
                "http://localhost:9000/test-bucket/file.txt?X-Amz-Signature=..."
            )
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            storage.presigned_url(key="file.txt")

            mock_client.presigned_get_object.assert_called_once()
            call_args = mock_client.presigned_get_object.call_args
            assert call_args[0][0] == "test-bucket"
            assert call_args[0][1] == "file.txt"

    def test_presigned_url_default_expiry(self):
        """presigned_url should default to 24 hour expiry."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            storage.presigned_url(key="file.txt")

            call_args = mock_client.presigned_get_object.call_args
            assert call_args[1]["expires"] == timedelta(hours=24)

    def test_presigned_url_custom_expiry(self):
        """presigned_url should support custom expiry times."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            storage.presigned_url(key="file.txt", expires_hours=48)

            call_args = mock_client.presigned_get_object.call_args
            assert call_args[1]["expires"] == timedelta(hours=48)

    def test_presigned_url_returns_url_string(self):
        """presigned_url should return the URL from the client."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            expected_url = "http://localhost:9000/bucket/key?signed"
            mock_client.presigned_get_object.return_value = expected_url
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            result = storage.presigned_url(key="key")

            assert result == expected_url


class TestMinIOStorageDelete:
    """Tests for file deletion functionality."""

    def test_delete_calls_remove_object(self):
        """delete should call remove_object with correct parameters."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            storage.delete(key="file-to-delete.txt")

            mock_client.remove_object.assert_called_once_with("test-bucket", "file-to-delete.txt")

    def test_delete_handles_nested_paths(self):
        """delete should handle nested paths correctly."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            storage.delete(key="path/to/nested/file.txt")

            mock_client.remove_object.assert_called_once_with(
                "test-bucket", "path/to/nested/file.txt"
            )


class TestMinIOStorageGet:
    """Tests for file download functionality."""

    def test_get_calls_get_object(self):
        """get should call get_object with correct parameters."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True

            mock_response = MagicMock()
            mock_response.read.return_value = b"file content"
            mock_client.get_object.return_value = mock_response
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            storage.get(key="file.txt")

            mock_client.get_object.assert_called_once_with("test-bucket", "file.txt")

    def test_get_returns_file_contents(self):
        """get should return the file contents as bytes."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True

            expected_content = b"This is the file content"
            mock_response = MagicMock()
            mock_response.read.return_value = expected_content
            mock_client.get_object.return_value = mock_response
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            result = storage.get(key="file.txt")

            assert result == expected_content

    def test_get_closes_response(self):
        """get should properly close and release the response connection."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True

            mock_response = MagicMock()
            mock_response.read.return_value = b"content"
            mock_client.get_object.return_value = mock_response
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            storage.get(key="file.txt")

            mock_response.close.assert_called_once()
            mock_response.release_conn.assert_called_once()

    def test_get_handles_binary_content(self):
        """get should handle binary content correctly."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True

            binary_content = bytes(range(256))
            mock_response = MagicMock()
            mock_response.read.return_value = binary_content
            mock_client.get_object.return_value = mock_response
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            result = storage.get(key="binary.bin")

            assert result == binary_content
            assert len(result) == 256


class TestMinIOStorageExists:
    """Tests for file existence check functionality."""

    def test_exists_returns_true_when_object_exists(self):
        """exists should return True when the object exists."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_client.stat_object.return_value = MagicMock()  # Object exists
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            result = storage.exists(key="existing-file.txt")

            assert result is True
            mock_client.stat_object.assert_called_once_with("test-bucket", "existing-file.txt")

    def test_exists_returns_false_when_object_missing(self):
        """exists should return False when the object doesn't exist."""
        from minio.error import S3Error

        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            # Simulate S3Error for missing object
            mock_client.stat_object.side_effect = S3Error(
                code="NoSuchKey",
                message="Object does not exist",
                resource="missing-file.txt",
                request_id="test",
                host_id="test",
                response=MagicMock(status=404),
            )
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            result = storage.exists(key="missing-file.txt")

            assert result is False


class TestMinIOStorageList:
    """Tests for listing objects functionality."""

    def test_list_calls_list_objects(self):
        """list should call list_objects with correct parameters."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_client.list_objects.return_value = iter([])
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            list(storage.list(prefix="uploads/"))

            mock_client.list_objects.assert_called_once_with(
                "test-bucket", prefix="uploads/", recursive=True
            )

    def test_list_returns_object_names(self):
        """list should yield object names."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True

            # Create mock objects
            mock_obj1 = MagicMock()
            mock_obj1.object_name = "uploads/file1.txt"
            mock_obj2 = MagicMock()
            mock_obj2.object_name = "uploads/file2.txt"
            mock_client.list_objects.return_value = iter([mock_obj1, mock_obj2])
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            result = list(storage.list(prefix="uploads/"))

            assert result == ["uploads/file1.txt", "uploads/file2.txt"]

    def test_list_with_empty_prefix(self):
        """list should work with empty prefix to list all objects."""
        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_client.list_objects.return_value = iter([])
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            list(storage.list(prefix=""))

            mock_client.list_objects.assert_called_once_with(
                "test-bucket", prefix="", recursive=True
            )


class TestMinIOStorageErrorHandling:
    """Tests for error handling in storage operations."""

    def test_upload_propagates_client_errors(self):
        """Upload should propagate errors from the MinIO client."""
        from minio.error import S3Error

        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_client.put_object.side_effect = S3Error(
                code="AccessDenied",
                message="Access Denied",
                resource="file.txt",
                request_id="test",
                host_id="test",
                response=MagicMock(status=403),
            )
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            with pytest.raises(S3Error):
                storage.upload(key="file.txt", data=b"data", content_type="text/plain")

    def test_get_propagates_not_found_error(self):
        """Get should propagate NotFound errors from the MinIO client."""
        from minio.error import S3Error

        with patch("semrush_core.storage.minio.Minio") as mock_minio_class:
            mock_client = MagicMock()
            mock_client.bucket_exists.return_value = True
            mock_client.get_object.side_effect = S3Error(
                code="NoSuchKey",
                message="Object does not exist",
                resource="missing.txt",
                request_id="test",
                host_id="test",
                response=MagicMock(status=404),
            )
            mock_minio_class.return_value = mock_client

            storage = MinIOStorage(
                endpoint="localhost:9000",
                access_key="minioadmin",
                secret_key="minioadmin",
                bucket="test-bucket",
            )

            with pytest.raises(S3Error):
                storage.get(key="missing.txt")
