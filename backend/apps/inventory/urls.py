"""API routes for the Inventory module.

Mounted under `/api/v1/inventory/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "inventory"

router = DefaultRouter()

urlpatterns = router.urls
