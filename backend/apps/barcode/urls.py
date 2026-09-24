"""API routes for the Barcode module.

Mounted under `/api/v1/barcode/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "barcode"

router = DefaultRouter()

urlpatterns = router.urls
