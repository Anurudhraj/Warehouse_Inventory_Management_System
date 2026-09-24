"""API routes for the Putaway module.

Mounted under `/api/v1/putaway/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "putaway"

router = DefaultRouter()

urlpatterns = router.urls
