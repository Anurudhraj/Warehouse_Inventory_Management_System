"""API routes for the Procurement module.

Mounted under `/api/v1/procurement/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "procurement"

router = DefaultRouter()

urlpatterns = router.urls
