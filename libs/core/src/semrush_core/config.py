"""
Application configuration using pydantic-settings.

All environment variables are validated on load. Required variables will raise
ValidationError if missing or invalid.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Required environment variables:
        - DATABASE_URL: PostgreSQL connection string (async driver)
        - REDIS_URL: Redis connection string
        - JWT_SECRET: Secret key for JWT signing (min 32 chars in production)

    Optional environment variables:
        - MINIO_*: Object storage configuration
        - CLICKHOUSE_*: Optional analytics database
        - GOOGLE_*: OAuth integration settings
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="Openahrush", description="Application name")
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment",
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    # Database (PostgreSQL with asyncpg)
    database_url: str = Field(
        ...,
        description="PostgreSQL connection URL (e.g., postgresql+asyncpg://user:pass@host:5432/db)",
    )
    database_pool_size: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Database connection pool size",
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        le=100,
        description="Maximum overflow connections beyond pool size",
    )
    database_pool_timeout: int = Field(
        default=30,
        ge=1,
        description="Timeout in seconds for getting connection from pool",
    )

    # Redis
    redis_url: str = Field(
        ...,
        description="Redis connection URL (e.g., redis://localhost:6379/0)",
    )

    # JWT Authentication
    jwt_secret: SecretStr = Field(
        ...,
        min_length=32,
        description="Secret key for JWT token signing (min 32 characters)",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        description="Access token expiration time in minutes",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        description="Refresh token expiration time in days",
    )

    # MinIO / S3 Object Storage
    minio_endpoint: str = Field(
        default="localhost:9000",
        description="MinIO/S3 endpoint address",
    )
    minio_access_key: SecretStr = Field(
        default=SecretStr("minioadmin"),
        description="MinIO/S3 access key",
    )
    minio_secret_key: SecretStr = Field(
        default=SecretStr("minioadmin"),
        description="MinIO/S3 secret key",
    )
    minio_secure: bool = Field(
        default=False,
        description="Use HTTPS for MinIO/S3 connections",
    )
    s3_bucket: str = Field(
        default="openahrush",
        description="Default S3 bucket name",
    )

    # ClickHouse (Optional - for Common Crawl analytics)
    clickhouse_url: str | None = Field(
        default=None,
        description="ClickHouse connection URL",
    )
    clickhouse_database: str = Field(
        default="openahrush",
        description="ClickHouse database name",
    )

    # Google OAuth (Optional)
    google_client_id: str | None = Field(
        default=None,
        description="Google OAuth client ID",
    )
    google_client_secret: SecretStr | None = Field(
        default=None,
        description="Google OAuth client secret",
    )
    google_redirect_uri: str | None = Field(
        default=None,
        description="Google OAuth redirect URI",
    )

    # Microsoft OAuth (Optional)
    microsoft_client_id: str | None = Field(
        default=None,
        description="Microsoft OAuth client ID",
    )
    microsoft_client_secret: SecretStr | None = Field(
        default=None,
        description="Microsoft OAuth client secret",
    )
    microsoft_redirect_uri: str | None = Field(
        default=None,
        description="Microsoft OAuth redirect URI",
    )

    # Encryption key for sensitive data storage
    encryption_key: SecretStr | None = Field(
        default=None,
        description="Fernet encryption key for token storage (32 bytes, base64 encoded)",
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API server port")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL uses async driver."""
        if not v.startswith(("postgresql+asyncpg://", "postgresql+psycopg://")):
            # Auto-convert standard postgresql:// to asyncpg
            if v.startswith("postgresql://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
            raise ValueError(
                "DATABASE_URL must use postgresql+asyncpg:// or postgresql+psycopg:// driver"
            )
        return v

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must start with redis:// or rediss://")
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Validate stricter requirements for production environment."""
        if self.environment == "production":
            if self.debug:
                raise ValueError("DEBUG must be False in production")
            if len(self.jwt_secret.get_secret_value()) < 64:
                raise ValueError("JWT_SECRET must be at least 64 characters in production")
            if self.encryption_key is None:
                raise ValueError("ENCRYPTION_KEY is required in production")
        return self

    @property
    def async_database_url(self) -> str:
        """Get the async-compatible database URL."""
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    Settings are loaded once and cached for the lifetime of the application.
    Use dependency injection in FastAPI to override for testing.

    Returns:
        Settings instance with validated configuration.

    Raises:
        ValidationError: If required environment variables are missing or invalid.
    """
    return Settings()  # type: ignore[call-arg]
