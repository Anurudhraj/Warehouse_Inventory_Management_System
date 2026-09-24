"""Cross-cutting HTTP middleware."""

from __future__ import annotations

import contextvars
import logging
import time
import uuid

from django.http import HttpRequest, HttpResponse

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

REQUEST_ID_HEADER = "X-Request-ID"

access_logger = logging.getLogger("access")
app_logger = logging.getLogger("apps.core")

# Paths whose query strings must never be written to logs (they carry
# credentials, tokens or one-time codes).
_SENSITIVE_PATH_MARKERS = (
    "/auth/login",
    "/auth/logout",
    "/auth/mfa",
    "/auth/password",
    "/auth/email",
    "/admin/login",
)


def get_current_request_id() -> str | None:
    return request_id_var.get()


class RequestContextMiddleware:
    """Assign/propagate a request id and expose it for tracing.

    Accepts an incoming ``X-Request-ID`` header (e.g. from the edge
    proxy) or generates a UUID, stores it in a context var for logging
    and echoes it back in the response.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming.strip()[:128] or uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[REQUEST_ID_HEADER] = request_id
        return response


class AccessLogMiddleware:
    """One structured access-log line per request (no bodies, no secrets)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        path = request.get_full_path()
        if any(marker in path for marker in _SENSITIVE_PATH_MARKERS):
            # Never log credential-carrying request paths in detail.
            path = path.split("?")[0] + " [redacted-query]"
        access_logger.info(
            "%s %s -> %s (%.1fms) rid=%s",
            request.method,
            path,
            response.status_code,
            duration_ms,
            getattr(request, "request_id", "-"),
        )
        return response
