"""API routes for the Orders module.

Mounted under `/api/v1/orders/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "orders"

router = DefaultRouter()

urlpatterns = router.urls
