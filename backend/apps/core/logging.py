"""Logging utilities.

* ``SensitiveDataFilter`` — redacts secrets (passwords, tokens, keys,
  cookies) from log records so sensitive data never reaches log output.
* ``RequestContextFilter`` — attaches the current request id to every
  record so lines from one request can be correlated.
"""

from __future__ import annotations

import logging
import re

# key=value / "key": value style secrets, matched case-insensitively
_SECRET_KEY_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|apikey|authorization|"
    r"csrf[_-]?token|sessionid|cookie|credentials?)\b(\s*[:=]\s*)\S+"
)

# Authorization / cookie headers carry a free-form credential: everything
# after the separator is sensitive, not just the first token.
_CREDENTIAL_HEADER_PATTERN = re.compile(
    r"(?i)\b(authorization|proxy-authorization|cookie|set-cookie|x-api-key|api-key)\b"
    r"(\s*[:=]\s*)[^\r\n]*"
)

_BEARER_PATTERN = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")

_SENSITIVE_ATTRS = ("password", "secret", "token", "api_key", "apikey", "authorization")


class SensitiveDataFilter(logging.Filter):
    """Redact credential-looking values from every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        cleaned = _CREDENTIAL_HEADER_PATTERN.sub(r"\1\2***", message)
        cleaned = _SECRET_KEY_PATTERN.sub(r"\1\2***", cleaned)
        cleaned = _BEARER_PATTERN.sub(r"\1 ***", cleaned)
        if cleaned != message:
            record.msg = cleaned
            record.args = ()

        if isinstance(record.args, dict):
            record.args = {
                key: ("***" if str(key).lower() in _SENSITIVE_ATTRS else value)
                for key, value in record.args.items()
            }
        return True


class RequestContextFilter(logging.Filter):
    """Attach the request id (see middleware) to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        from apps.core.middleware import get_current_request_id

        if not hasattr(record, "request_id"):
            record.request_id = get_current_request_id() or "-"
        return True
