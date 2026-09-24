"""API routes for the Returns module.

Mounted under `/api/v1/returns/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "returns"

router = DefaultRouter()

urlpatterns = router.urls
