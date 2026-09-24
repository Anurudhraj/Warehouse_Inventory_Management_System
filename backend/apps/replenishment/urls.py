"""API routes for the Replenishment module.

Mounted under `/api/v1/replenishment/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "replenishment"

router = DefaultRouter()

urlpatterns = router.urls
