"""TOTP (RFC 6238) implementation used for MFA.

Implemented directly on the standard library so the authentication stack has
no third-party runtime dependency for MFA. Compatible with Google
Authenticator, Authy, 1Password, Microsoft Authenticator and any RFC 6238
client (HMAC-SHA1, 6 digits, 30-second step — the interoperable defaults).

Verified against the RFC 6238 Appendix B test vectors in the test suite.
"""
from __future__ import annotations

import base64
import hmac
import secrets
import struct
import time
from hashlib import sha1
from urllib.parse import quote, urlencode

DEFAULT_DIGITS = 6
DEFAULT_STEP_SECONDS = 30
DEFAULT_ALGORITHM = "SHA1"
_ALGORITHMS = {"SHA1": sha1}


def generate_secret(length: int = 20) -> str:
    """Return a new base32 secret (160 bits by default, per RFC 4226 §4)."""
    return base64.b32encode(secrets.token_bytes(length)).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    normalized = secret.strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    return base64.b32decode(normalized + padding, casefold=True)


def _hotp(secret: str, counter: int, digits: int = DEFAULT_DIGITS) -> str:
    digest = hmac.new(_decode_secret(secret), struct.pack(">Q", counter), sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(binary % (10**digits)).zfill(digits)


def generate_code(
    secret: str,
    *,
    at_time: float | None = None,
    step: int = DEFAULT_STEP_SECONDS,
    digits: int = DEFAULT_DIGITS,
) -> str:
    """Current TOTP code for ``secret`` (``at_time`` is a UNIX timestamp)."""
    timestamp = time.time() if at_time is None else at_time
    return _hotp(secret, int(timestamp // step), digits)


def verify_code(
    secret: str,
    code: str,
    *,
    at_time: float | None = None,
    step: int = DEFAULT_STEP_SECONDS,
    digits: int = DEFAULT_DIGITS,
    window: int = 1,
    last_used_step: int | None = None,
) -> bool:
    """Constant-time verification of ``code`` within ``±window`` steps.

    ``last_used_step`` (when provided) rejects replay of a code that was
    already accepted — callers persist the returned step from
    :func:`code_step`.
    """
    candidate = (code or "").strip().replace(" ", "")
    if not candidate.isdigit() or len(candidate) != digits:
        return False

    timestamp = time.time() if at_time is None else at_time
    current_step = int(timestamp // step)

    verified = False
    accepted_step = None
    for offset in range(-window, window + 1):
        candidate_step = current_step + offset
        if last_used_step is not None and candidate_step <= last_used_step:
            continue
        expected = _hotp(secret, candidate_step, digits)
        if hmac.compare_digest(expected, candidate):
            verified = True
            accepted_step = candidate_step

    if verified and accepted_step is not None:
        verify_code.last_accepted_step = accepted_step  # type: ignore[attr-defined]
    return verified


def code_step(at_time: float | None = None, *, step: int = DEFAULT_STEP_SECONDS) -> int:
    """Current time-step index (used for replay protection bookkeeping)."""
    timestamp = time.time() if at_time is None else at_time
    return int(timestamp // step)


def build_otpauth_uri(
    secret: str,
    *,
    account_name: str,
    issuer: str,
    digits: int = DEFAULT_DIGITS,
    step: int = DEFAULT_STEP_SECONDS,
) -> str:
    """``otpauth://`` provisioning URI for authenticator apps / QR codes."""
    label = quote(f"{issuer}:{account_name}", safe="")
    params = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": DEFAULT_ALGORITHM,
            "digits": digits,
            "period": step,
        }
    )
    return f"otpauth://totp/{label}?{params}"


def generate_recovery_codes(count: int = 10, groups: int = 2, group_length: int = 5) -> list[str]:
    """Human-transferable single-use recovery codes (e.g. ``4F9KA-7XQ2M``)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous characters
    codes: list[str] = []
    while len(codes) < count:
        code = "-".join(
            "".join(secrets.choice(alphabet) for _ in range(group_length)) for _ in range(groups)
        )
        if code not in codes:
            codes.append(code)
    return codes
