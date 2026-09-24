"""API routes for the Locations module.

Mounted under `/api/v1/locations/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "locations"

router = DefaultRouter()

urlpatterns = router.urls
