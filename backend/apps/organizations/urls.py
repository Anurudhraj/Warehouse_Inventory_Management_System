"""API routes for the Organizations module.

Mounted under `/api/v1/organizations/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "organizations"

router = DefaultRouter()

urlpatterns = router.urls
