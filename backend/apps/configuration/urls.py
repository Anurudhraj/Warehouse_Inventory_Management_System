"""API routes for the Configuration module.

Mounted under `/api/v1/configuration/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "configuration"

router = DefaultRouter()

urlpatterns = router.urls
