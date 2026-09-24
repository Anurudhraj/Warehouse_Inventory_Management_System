"""API routes for the Products module.

Mounted under `/api/v1/products/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "products"

router = DefaultRouter()

urlpatterns = router.urls
