"""Root URL configuration.

API surface:

    /api/v1/…            versioned REST API (see config.api_urls)
    /api/v1/schema/      OpenAPI 3 schema
    /api/v1/docs/        Swagger UI
    /api/v1/redoc/       ReDoc

API documentation endpoints are disabled in production unless
``ENABLE_API_DOCS=true`` is set.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.core.views_error import page_not_found, server_error

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(("config.api_urls", "api"), namespace="v1")),
]

if getattr(settings, "ENABLE_API_DOCS", True):
    urlpatterns += [
        path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/v1/docs/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path(
            "api/v1/redoc/",
            SpectacularRedocView.as_view(url_name="schema"),
            name="redoc",
        ),
    ]

handler404 = page_not_found
handler500 = server_error
