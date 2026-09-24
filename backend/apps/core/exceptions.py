"""Centralised API error handling.

* Standard DRF ``APIException`` subclasses are rendered as JSON errors.
* Validation errors keep DRF's field-level detail.
* Unexpected exceptions are logged (with the request id) and returned
  to clients as a generic 500 payload — stack traces and internal
  details never leak into responses.
"""

from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import set_rollback

logger = logging.getLogger("apps.core.exceptions")


def _error_payload(code: str, message: str, detail=None) -> dict:
    payload: dict = {"error": {"code": code, "message": message}}
    if detail is not None:
        payload["error"]["detail"] = detail
    return payload


def exception_handler(exc, context):
    """DRF exception handler used by every API view."""
    request = context.get("request")
    request_id = getattr(request, "request_id", None) if request else None

    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    if isinstance(exc, exceptions.APIException):
        set_rollback()
        payload = _error_payload(
            code=exc.default_code or "error",
            message=str(exc.detail) if isinstance(exc.detail, str) else exc.default_detail,
            detail=exc.detail if not isinstance(exc.detail, str) else None,
        )
        headers = {}
        if getattr(exc, "auth_header", None):
            headers["WWW-Authenticate"] = exc.auth_header
        if getattr(exc, "wait", None):
            headers["Retry-After"] = str(exc.wait)
        response = Response(payload, status=exc.status_code, headers=headers)
        if request_id:
            response["X-Request-ID"] = request_id
        return response

    # Unexpected error: log with context, return a safe generic response.
    logger.exception(
        "Unhandled exception on %s %s rid=%s",
        getattr(request, "method", "?"),
        getattr(request, "path", "?"),
        request_id or "-",
    )
    set_rollback()
    response = Response(
        _error_payload(
            code="internal_error",
            message="An unexpected error occurred. Reference id provided to support.",
        ),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    if request_id:
        response["X-Request-ID"] = request_id
    return response
