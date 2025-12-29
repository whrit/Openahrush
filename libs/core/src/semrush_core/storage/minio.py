"""
MinIO storage utilities for object storage operations.

Provides a wrapper around the MinIO client for common storage operations
including upload, download, presigned URLs, and object management.
"""

import io
from collections.abc import Iterator
from datetime import timedelta

from minio import Minio
from minio.error import S3Error


class MinIOStorage:
    """
    MinIO storage client wrapper for S3-compatible object storage.

    This class provides a simplified interface for common storage operations:
    - Uploading files with content type support
    - Generating presigned URLs for temporary access
    - Downloading file contents
    - Deleting objects
    - Checking object existence
    - Listing objects by prefix

    Example:
        storage = MinIOStorage(
            endpoint="localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            bucket="my-bucket"
        )
        uri = storage.upload("reports/report.pdf", pdf_bytes, "application/pdf")
        url = storage.presigned_url("reports/report.pdf", expires_hours=1)
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ) -> None:
        """
        Initialize MinIO storage client.

        Args:
            endpoint: MinIO server endpoint (e.g., "localhost:9000")
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket: Default bucket name for operations
            secure: Use HTTPS if True, HTTP if False (default: False)
        """
        self.client = Minio(endpoint, access_key, secret_key, secure=secure)
        self.bucket = bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist."""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload(self, key: str, data: bytes, content_type: str) -> str:
        """
        Upload data to object storage.

        Args:
            key: Object key (path) in the bucket
            data: Binary data to upload
            content_type: MIME type of the content

        Returns:
            S3 URI of the uploaded object (e.g., "s3://bucket/key")
        """
        self.client.put_object(
            self.bucket,
            key,
            io.BytesIO(data),
            len(data),
            content_type=content_type,
        )
        return f"s3://{self.bucket}/{key}"

    def presigned_url(self, key: str, expires_hours: int = 24) -> str:
        """
        Generate a presigned URL for temporary object access.

        Args:
            key: Object key (path) in the bucket
            expires_hours: URL expiration time in hours (default: 24)

        Returns:
            Presigned URL string for GET access
        """
        return self.client.presigned_get_object(
            self.bucket, key, expires=timedelta(hours=expires_hours)
        )

    def delete(self, key: str) -> None:
        """
        Delete an object from storage.

        Args:
            key: Object key (path) to delete
        """
        self.client.remove_object(self.bucket, key)

    def get(self, key: str) -> bytes:
        """
        Download object contents.

        Args:
            key: Object key (path) to download

        Returns:
            Object contents as bytes

        Raises:
            S3Error: If the object doesn't exist or access is denied
        """
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def exists(self, key: str) -> bool:
        """
        Check if an object exists in storage.

        Args:
            key: Object key (path) to check

        Returns:
            True if object exists, False otherwise
        """
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except S3Error:
            return False

    def list(self, prefix: str = "") -> Iterator[str]:
        """
        List objects with a given prefix.

        Args:
            prefix: Key prefix to filter objects (default: "" for all)

        Yields:
            Object names matching the prefix
        """
        objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
        for obj in objects:
            yield obj.object_name
