"""API routes for the Security module.

Mounted under `/api/v1/security/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "security"

router = DefaultRouter()

urlpatterns = router.urls
