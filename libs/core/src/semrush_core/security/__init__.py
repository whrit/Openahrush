"""
Security utilities for Openahrush.

Provides:
- Password hashing and verification (bcrypt)
- JWT token creation and validation
- Fernet encryption for sensitive data storage
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
]
