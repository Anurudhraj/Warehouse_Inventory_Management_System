"""API routes for the Receiving module.

Mounted under `/api/v1/receiving/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "receiving"

router = DefaultRouter()

urlpatterns = router.urls
