"""
Fernet encryption for sensitive data storage.

Used to encrypt OAuth tokens, API keys, and other sensitive data
before storing in the database. Provides symmetric encryption with
authenticated encryption (AE) guarantees.
"""

import base64
import secrets
from typing import overload

from cryptography.fernet import Fernet, InvalidToken

from semrush_core.config import get_settings


class EncryptionError(Exception):
    """Base exception for encryption-related errors."""

    pass


class EncryptionKeyMissingError(EncryptionError):
    """Raised when encryption key is not configured."""

    pass


class DecryptionError(EncryptionError):
    """Raised when decryption fails (invalid key or corrupted data)."""

    pass


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.

    Use this to create a key for the ENCRYPTION_KEY environment variable.
    The key is URL-safe base64 encoded.

    Returns:
        Base64-encoded 32-byte key suitable for ENCRYPTION_KEY env var.

    Example:
        >>> key = generate_encryption_key()
        >>> len(base64.urlsafe_b64decode(key)) == 32
        True
    """
    return Fernet.generate_key().decode("utf-8")


def _get_fernet() -> Fernet:
    """
    Get a Fernet instance configured with the encryption key.

    Returns:
        Configured Fernet instance.

    Raises:
        EncryptionKeyMissingError: If ENCRYPTION_KEY is not set.
    """
    settings = get_settings()

    if settings.encryption_key is None:
        raise EncryptionKeyMissingError(
            "ENCRYPTION_KEY environment variable is not set. "
            "Generate one with: python -c 'from semrush_core.security import generate_encryption_key; print(generate_encryption_key())'"
        )

    try:
        return Fernet(settings.encryption_key.get_secret_value().encode())
    except Exception as e:
        raise EncryptionError(f"Invalid encryption key format: {e}") from e


@overload
def encrypt_token(plaintext: str) -> str: ...


@overload
def encrypt_token(plaintext: bytes) -> bytes: ...


def encrypt_token(plaintext: str | bytes) -> str | bytes:
    """
    Encrypt sensitive data using Fernet.

    Fernet guarantees that data encrypted cannot be manipulated or
    read without the key. It uses AES-128-CBC with HMAC-SHA256.

    Args:
        plaintext: Data to encrypt (string or bytes).

    Returns:
        Encrypted data in the same type as input.

    Raises:
        EncryptionKeyMissingError: If encryption key is not configured.
        EncryptionError: If encryption fails.

    Example:
        >>> encrypted = encrypt_token("oauth_access_token_value")
        >>> encrypted != "oauth_access_token_value"
        True
    """
    fernet = _get_fernet()

    is_string = isinstance(plaintext, str)
    data = plaintext.encode("utf-8") if is_string else plaintext

    try:
        encrypted = fernet.encrypt(data)
        return encrypted.decode("utf-8") if is_string else encrypted
    except Exception as e:
        raise EncryptionError(f"Encryption failed: {e}") from e


@overload
def decrypt_token(ciphertext: str) -> str: ...


@overload
def decrypt_token(ciphertext: bytes) -> bytes: ...


def decrypt_token(ciphertext: str | bytes) -> str | bytes:
    """
    Decrypt data encrypted with encrypt_token.

    Args:
        ciphertext: Encrypted data (string or bytes).

    Returns:
        Decrypted data in the same type as input.

    Raises:
        EncryptionKeyMissingError: If encryption key is not configured.
        DecryptionError: If decryption fails (wrong key or corrupted data).

    Example:
        >>> encrypted = encrypt_token("secret_value")
        >>> decrypt_token(encrypted)
        'secret_value'
    """
    fernet = _get_fernet()

    is_string = isinstance(ciphertext, str)
    data = ciphertext.encode("utf-8") if is_string else ciphertext

    try:
        decrypted = fernet.decrypt(data)
        return decrypted.decode("utf-8") if is_string else decrypted
    except InvalidToken as e:
        raise DecryptionError(
            "Decryption failed. This may be due to: "
            "1) Wrong encryption key, "
            "2) Corrupted ciphertext, or "
            "3) Token was encrypted with a different key"
        ) from e
    except Exception as e:
        raise DecryptionError(f"Decryption failed: {e}") from e


def encrypt_dict_values(
    data: dict[str, str],
    keys_to_encrypt: list[str] | None = None,
) -> dict[str, str]:
    """
    Encrypt specified values in a dictionary.

    Useful for encrypting OAuth token responses where only certain
    fields contain sensitive data.

    Args:
        data: Dictionary with string values.
        keys_to_encrypt: Keys whose values should be encrypted.
                        If None, encrypts all values.

    Returns:
        Dictionary with specified values encrypted.

    Example:
        >>> tokens = {"access_token": "secret", "token_type": "Bearer"}
        >>> encrypted = encrypt_dict_values(tokens, ["access_token"])
        >>> encrypted["token_type"]  # Not encrypted
        'Bearer'
    """
    result = data.copy()
    keys = keys_to_encrypt or list(data.keys())

    for key in keys:
        if key in result and result[key]:
            result[key] = encrypt_token(result[key])

    return result


def decrypt_dict_values(
    data: dict[str, str],
    keys_to_decrypt: list[str] | None = None,
) -> dict[str, str]:
    """
    Decrypt specified values in a dictionary.

    Args:
        data: Dictionary with some encrypted string values.
        keys_to_decrypt: Keys whose values should be decrypted.
                        If None, attempts to decrypt all values.

    Returns:
        Dictionary with specified values decrypted.
    """
    result = data.copy()
    keys = keys_to_decrypt or list(data.keys())

    for key in keys:
        if key in result and result[key]:
            result[key] = decrypt_token(result[key])

    return result


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.

    Useful for generating API keys, session tokens, or CSRF tokens.

    Args:
        length: Number of random bytes (output will be longer due to encoding).

    Returns:
        URL-safe base64-encoded random token.

    Example:
        >>> token = generate_secure_token(32)
        >>> len(token) >= 32
        True
    """
    return secrets.token_urlsafe(length)
