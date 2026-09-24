"""Secret encryption helpers.

MFA (TOTP) secrets must be recoverable to verify codes, so they cannot be
hashed — they are encrypted at rest with a key derived from ``SECRET_KEY``
via HKDF-SHA256 and a fixed application salt. Rotating ``SECRET_KEY``
therefore requires re-enrolling MFA devices (documented in docs/rbac.md).
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

_CONTEXT = b"wims.mfa.totp.secret.v1"


class SecretDecryptionError(RuntimeError):
    """Raised when a stored secret cannot be decrypted (wrong/rotated key)."""


def _derive_key(secret_key: str) -> bytes:
    """HKDF-SHA256(SECRET_KEY, salt=app context) → 32-byte urlsafe key."""
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        secret_key.encode("utf-8"),
        _CONTEXT,
        iterations=100_000,
        dklen=32,
    )
    return base64.urlsafe_b64encode(derived)


def _fernet() -> Fernet:
    return Fernet(_derive_key(settings.SECRET_KEY))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret for storage (returns a URL-safe token)."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    """Decrypt a stored secret; raises :class:`SecretDecryptionError` on failure."""
    if not token:
        raise SecretDecryptionError("No secret stored.")
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise SecretDecryptionError("Stored secret could not be decrypted.") from exc


def hash_token(raw_token: str) -> str:
    """Stable, non-reversible digest for one-time tokens.

    A plain SHA-256 is appropriate here (unlike passwords): tokens are
    high-entropy random values, so brute force is infeasible, and hashing
    keeps lookup a single indexed query.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
