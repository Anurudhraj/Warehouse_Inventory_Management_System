"""API routes for the Warehouses module.

Mounted under `/api/v1/warehouses/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "warehouses"

router = DefaultRouter()

urlpatterns = router.urls
