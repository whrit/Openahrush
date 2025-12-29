"""
Security utilities for Openahrush.

Provides:
- Password hashing and verification (bcrypt)
- JWT token creation and validation
- Fernet encryption for sensitive data storage
- SSRF prevention for webhook URLs
"""

from semrush_core.security.encryption import (
    decrypt_token,
    encrypt_token,
    generate_encryption_key,
)
from semrush_core.security.jwt import (
    TokenData,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from semrush_core.security.password import (
    hash_password,
    verify_password,
)
from semrush_core.security.ssrf import (
    BLOCKED_NETWORKS,
    ValidationResult,
    is_internal_hostname,
    is_private_ip,
    resolve_and_validate_host,
    validate_url_format,
    validate_webhook_url,
)

__all__ = [
    # Password
    "hash_password",
    "verify_password",
    # JWT
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "TokenData",
    # Encryption
    "encrypt_token",
    "decrypt_token",
    "generate_encryption_key",
    # SSRF Prevention
    "validate_webhook_url",
    "validate_url_format",
    "resolve_and_validate_host",
    "is_private_ip",
    "is_internal_hostname",
    "ValidationResult",
    "BLOCKED_NETWORKS",
]
