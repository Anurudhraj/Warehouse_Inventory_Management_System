"""API routes for the Reports module.

Mounted under `/api/v1/reports/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "reports"

router = DefaultRouter()

urlpatterns = router.urls
