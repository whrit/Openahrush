"""
MinIO/S3 storage service for export artifacts.

Provides:
- File upload to MinIO/S3
- Presigned URL generation for downloads
- File deletion and lifecycle management
"""

from __future__ import annotations

import io
from datetime import timedelta
from typing import BinaryIO
from uuid import UUID

from minio import Minio
from minio.error import S3Error

from semrush_core import get_settings


class StorageError(Exception):
    """Exception raised for storage operations failures."""

    pass


class MinIOStorage:
    """
    MinIO/S3 storage client for export artifacts.

    Handles file upload, download URL generation, and cleanup.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        secure: bool | None = None,
    ) -> None:
        """
        Initialize MinIO storage client.

        Args:
            endpoint: MinIO endpoint (defaults to settings).
            access_key: Access key (defaults to settings).
            secret_key: Secret key (defaults to settings).
            bucket: Default bucket name (defaults to settings).
            secure: Use HTTPS (defaults to settings).
        """
        settings = get_settings()

        self.endpoint = endpoint or settings.minio_endpoint
        self.access_key = access_key or settings.minio_access_key.get_secret_value()
        self.secret_key = secret_key or settings.minio_secret_key.get_secret_value()
        self.bucket = bucket or settings.s3_bucket
        self.secure = secure if secure is not None else settings.minio_secure

        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create bucket if it doesn't exist."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            raise StorageError(f"Failed to ensure bucket exists: {e}") from e

    def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        bucket: str | None = None,
    ) -> str:
        """
        Upload file to storage.

        Args:
            key: Object key (path within bucket).
            data: File contents as bytes.
            content_type: MIME type of the file.
            bucket: Bucket name (defaults to configured bucket).

        Returns:
            S3 URI (s3://bucket/key).

        Raises:
            StorageError: If upload fails.
        """
        bucket = bucket or self.bucket

        try:
            self.client.put_object(
                bucket,
                key,
                io.BytesIO(data),
                len(data),
                content_type=content_type,
            )
            return f"s3://{bucket}/{key}"
        except S3Error as e:
            raise StorageError(f"Failed to upload object: {e}") from e

    def upload_stream(
        self,
        key: str,
        stream: BinaryIO,
        length: int,
        content_type: str = "application/octet-stream",
        bucket: str | None = None,
    ) -> str:
        """
        Upload file stream to storage.

        Args:
            key: Object key (path within bucket).
            stream: File-like object with read method.
            length: Content length in bytes.
            content_type: MIME type of the file.
            bucket: Bucket name (defaults to configured bucket).

        Returns:
            S3 URI (s3://bucket/key).

        Raises:
            StorageError: If upload fails.
        """
        bucket = bucket or self.bucket

        try:
            self.client.put_object(
                bucket,
                key,
                stream,
                length,
                content_type=content_type,
            )
            return f"s3://{bucket}/{key}"
        except S3Error as e:
            raise StorageError(f"Failed to upload object: {e}") from e

    def presigned_url(
        self,
        key: str,
        expires_hours: int = 24,
        bucket: str | None = None,
    ) -> str:
        """
        Generate presigned download URL.

        Args:
            key: Object key (path within bucket).
            expires_hours: URL expiration in hours.
            bucket: Bucket name (defaults to configured bucket).

        Returns:
            Presigned download URL.

        Raises:
            StorageError: If URL generation fails.
        """
        bucket = bucket or self.bucket

        try:
            return self.client.presigned_get_object(
                bucket,
                key,
                expires=timedelta(hours=expires_hours),
            )
        except S3Error as e:
            raise StorageError(f"Failed to generate presigned URL: {e}") from e

    def delete(
        self,
        key: str,
        bucket: str | None = None,
    ) -> None:
        """
        Delete file from storage.

        Args:
            key: Object key (path within bucket).
            bucket: Bucket name (defaults to configured bucket).

        Raises:
            StorageError: If deletion fails.
        """
        bucket = bucket or self.bucket

        try:
            self.client.remove_object(bucket, key)
        except S3Error as e:
            raise StorageError(f"Failed to delete object: {e}") from e

    def exists(
        self,
        key: str,
        bucket: str | None = None,
    ) -> bool:
        """
        Check if file exists in storage.

        Args:
            key: Object key (path within bucket).
            bucket: Bucket name (defaults to configured bucket).

        Returns:
            True if file exists.
        """
        bucket = bucket or self.bucket

        try:
            self.client.stat_object(bucket, key)
            return True
        except S3Error:
            return False

    def get_size(
        self,
        key: str,
        bucket: str | None = None,
    ) -> int | None:
        """
        Get file size in bytes.

        Args:
            key: Object key (path within bucket).
            bucket: Bucket name (defaults to configured bucket).

        Returns:
            File size in bytes, or None if not found.
        """
        bucket = bucket or self.bucket

        try:
            stat = self.client.stat_object(bucket, key)
            return stat.size
        except S3Error:
            return None


class ExportStorage:
    """
    High-level storage service for exports.

    Provides convenience methods for export-specific operations.
    """

    def __init__(self, storage: MinIOStorage | None = None) -> None:
        """
        Initialize export storage.

        Args:
            storage: MinIO storage instance (creates new if not provided).
        """
        self.storage = storage or MinIOStorage()

    def get_export_key(
        self,
        project_id: UUID,
        export_id: UUID,
        format: str,
    ) -> str:
        """
        Generate storage key for export file.

        Args:
            project_id: Project UUID.
            export_id: Export UUID.
            format: Export format (csv, json, pdf).

        Returns:
            Storage key path.
        """
        return f"exports/{project_id}/{export_id}.{format}"

    def get_content_type(self, format: str) -> str:
        """
        Get MIME type for export format.

        Args:
            format: Export format.

        Returns:
            MIME type string.
        """
        content_types = {
            "csv": "text/csv; charset=utf-8",
            "json": "application/json; charset=utf-8",
            "jsonl": "application/x-ndjson; charset=utf-8",
            "pdf": "application/pdf",
        }
        return content_types.get(format, "application/octet-stream")

    async def store_export(
        self,
        project_id: UUID,
        export_id: UUID,
        format: str,
        data: bytes,
    ) -> tuple[str, int, str]:
        """
        Store export file and generate download URL.

        Args:
            project_id: Project UUID.
            export_id: Export UUID.
            format: Export format.
            data: File contents.

        Returns:
            Tuple of (artifact_key, file_size, download_url).
        """
        key = self.get_export_key(project_id, export_id, format)
        content_type = self.get_content_type(format)

        # Upload file
        self.storage.upload(key, data, content_type)

        # Generate presigned URL (valid for 7 days)
        download_url = self.storage.presigned_url(key, expires_hours=168)

        return key, len(data), download_url

    async def refresh_download_url(
        self,
        artifact_key: str,
        expires_hours: int = 168,
    ) -> str:
        """
        Generate new presigned URL for existing export.

        Args:
            artifact_key: Storage key of the export.
            expires_hours: URL expiration in hours.

        Returns:
            New presigned download URL.
        """
        return self.storage.presigned_url(artifact_key, expires_hours)

    async def delete_export(
        self,
        artifact_key: str,
    ) -> None:
        """
        Delete export file from storage.

        Args:
            artifact_key: Storage key of the export.
        """
        self.storage.delete(artifact_key)

    async def cleanup_old_exports(
        self,
        project_id: UUID,
        keep_count: int = 10,
    ) -> list[str]:
        """
        Clean up old exports for a project.

        Keeps the most recent exports and deletes the rest.

        Args:
            project_id: Project UUID.
            keep_count: Number of exports to keep.

        Returns:
            List of deleted object keys.

        Note:
            This is a placeholder - actual implementation would need
            to list objects and sort by creation date.
        """
        # TODO: Implement cleanup logic with object listing
        return []
