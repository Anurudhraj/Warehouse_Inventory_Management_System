"""API routes for the Audit module.

Mounted under `/api/v1/audit/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "audit"

router = DefaultRouter()

urlpatterns = router.urls
