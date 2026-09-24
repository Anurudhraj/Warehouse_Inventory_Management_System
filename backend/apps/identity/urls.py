"""API routes for the Identity module.

Mounted under `/api/v1/identity/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "identity"

router = DefaultRouter()

urlpatterns = router.urls
