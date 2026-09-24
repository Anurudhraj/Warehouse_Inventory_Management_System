"""API routes for the Pricing module.

Mounted under `/api/v1/pricing/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "pricing"

router = DefaultRouter()

urlpatterns = router.urls
