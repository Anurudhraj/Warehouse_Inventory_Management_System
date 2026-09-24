"""JSON error handlers for requests outside DRF views (404/500)."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.defaults import page_not_found as html_page_not_found
from django.views.defaults import server_error as html_server_error


def _wants_api(request: HttpRequest) -> bool:
    return request.path.startswith("/api/") or "application/json" in request.headers.get(
        "Accept", ""
    )


def page_not_found(request: HttpRequest, exception=None):
    if _wants_api(request):
        return JsonResponse(
            {"error": {"code": "not_found", "message": "Resource not found."}},
            status=404,
        )
    return html_page_not_found(request, exception)


def server_error(request: HttpRequest):
    if _wants_api(request):
        return JsonResponse(
            {"error": {"code": "internal_error", "message": "Internal server error."}},
            status=500,
        )
    return html_server_error(request)
