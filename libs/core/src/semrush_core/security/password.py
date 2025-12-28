"""
Password hashing and verification using bcrypt.

Uses bcrypt directly for secure password handling.
"""

import bcrypt


def _ensure_bytes(value: str | bytes) -> bytes:
    """Ensure value is bytes."""
    if isinstance(value, str):
        return value.encode("utf-8")
    return value


def hash_password(password: str, *, rounds: int = 12) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password to hash.
        rounds: Cost factor (2^rounds iterations). Default is 12.

    Returns:
        Bcrypt hash string (includes salt and algorithm info).

    Example:
        >>> hashed = hash_password("my_secure_password")
        >>> hashed.startswith("$2b$")
        True
    """
    password_bytes = _ensure_bytes(password)
    salt = bcrypt.gensalt(rounds=rounds)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        plain_password: Plain text password to verify.
        hashed_password: Bcrypt hash to compare against.

    Returns:
        True if the password matches, False otherwise.

    Example:
        >>> hashed = hash_password("secret")
        >>> verify_password("secret", hashed)
        True
        >>> verify_password("wrong", hashed)
        False
    """
    password_bytes = _ensure_bytes(plain_password)
    hashed_bytes = _ensure_bytes(hashed_password)
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def needs_rehash(hashed_password: str, *, min_rounds: int = 12) -> bool:
    """
    Check if a password hash needs to be upgraded.

    Returns True if the hash uses fewer rounds than specified,
    indicating it should be rehashed on the user's next successful login.

    Args:
        hashed_password: Existing bcrypt hash.
        min_rounds: Minimum acceptable rounds. Default is 12.

    Returns:
        True if the hash should be updated, False otherwise.
    """
    # Extract the rounds from the hash
    # bcrypt hash format: $2b$XX$... where XX is the rounds
    try:
        parts = hashed_password.split("$")
        if len(parts) >= 3:
            current_rounds = int(parts[2])
            return current_rounds < min_rounds
    except (ValueError, IndexError):
        pass
    return True  # If we can't parse, assume it needs rehashing
