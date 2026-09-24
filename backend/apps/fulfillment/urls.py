"""API routes for the Fulfillment module.

Mounted under `/api/v1/fulfillment/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "fulfillment"

router = DefaultRouter()

urlpatterns = router.urls
