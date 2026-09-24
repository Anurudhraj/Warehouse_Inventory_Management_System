"""API routes for the RFID module.

Mounted under `/api/v1/rfid/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "rfid"

router = DefaultRouter()

urlpatterns = router.urls
