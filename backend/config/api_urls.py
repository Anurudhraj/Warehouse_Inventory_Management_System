"""Versioned API v1 URL structure.

This module is included at ``/api/v1/`` (namespace ``v1``) by
``config.urls``. Every domain module gets its own sub-path; business
endpoints are added there as modules are implemented.

    /api/v1/health/          core platform endpoints
    /api/v1/identity/        identity & access
    /api/v1/organizations/   ...
    /api/v1/warehouses/
    ...
"""

from django.conf import settings
from django.urls import include, path

urlpatterns = [
    path("", include("apps.core.urls")),
]

for _module in settings.DOMAIN_MODULES:
    urlpatterns.append(path(f"{_module}/", include(f"apps.{_module}.urls")))
