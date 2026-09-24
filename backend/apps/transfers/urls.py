"""API routes for the Transfers module.

Mounted under `/api/v1/transfers/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "transfers"

router = DefaultRouter()

urlpatterns = router.urls
