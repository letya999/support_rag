"""
Cryptographic Utilities

Provides secure hashing and verification for secrets.
Uses PBKDF2-HMAC-SHA256 from Python's hashlib (no external dependencies).
"""

import hashlib
import secrets
import hmac
from typing import Tuple


# PBKDF2 parameters
PBKDF2_ITERATIONS = 100000  # OWASP recommendation
SALT_LENGTH = 32  # bytes
HASH_LENGTH = 32  # bytes


def hash_secret(secret: str) -> str:
    """
    Hash a secret using PBKDF2-HMAC-SHA256.

    Args:
        secret: The plaintext secret to hash

    Returns:
        Hashed secret in format: algorithm$iterations$salt$hash
        Example: pbkdf2_sha256$100000$<salt_hex>$<hash_hex>
    """
    if not secret:
        raise ValueError("Secret cannot be empty")

    # Generate random salt
    salt = secrets.token_bytes(SALT_LENGTH)

    # Hash the secret
    key = hashlib.pbkdf2_hmac(
        'sha256',
        secret.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS,
        dklen=HASH_LENGTH
    )

    # Encode to hex
    salt_hex = salt.hex()
    hash_hex = key.hex()

    # Return in format that includes algorithm and parameters
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt_hex}${hash_hex}"


def verify_secret(secret: str, hashed: str) -> bool:
    """
    Verify a secret against a hashed value.

    Args:
        secret: The plaintext secret to verify
        hashed: The hashed secret from hash_secret()

    Returns:
        True if secret matches, False otherwise
    """
    if not secret or not hashed:
        return False

    try:
        # Parse the hashed value
        parts = hashed.split('$')
        if len(parts) != 4:
            return False

        algorithm, iterations_str, salt_hex, expected_hash_hex = parts

        if algorithm != 'pbkdf2_sha256':
            return False

        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)

        # Hash the provided secret with the same salt
        key = hashlib.pbkdf2_hmac(
            'sha256',
            secret.encode('utf-8'),
            salt,
            iterations,
            dklen=HASH_LENGTH
        )

        computed_hash_hex = key.hex()

        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(computed_hash_hex, expected_hash_hex)

    except Exception:
        return False


def generate_secret(length: int = 32) -> str:
    """
    Generate a cryptographically secure random secret.

    Args:
        length: Length of the secret in bytes (default: 32)

    Returns:
        Hex-encoded random secret
    """
    return secrets.token_hex(length)


def generate_salt() -> bytes:
    """
    Generate a cryptographically secure random salt.

    Returns:
        Random bytes suitable for use as a salt
    """
    return secrets.token_bytes(SALT_LENGTH)
