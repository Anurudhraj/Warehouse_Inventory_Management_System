"""API routes for the Suppliers module.

Mounted under `/api/v1/suppliers/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "suppliers"

router = DefaultRouter()

urlpatterns = router.urls
