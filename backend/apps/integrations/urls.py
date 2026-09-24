"""API routes for the Integrations module.

Mounted under `/api/v1/integrations/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "integrations"

router = DefaultRouter()

urlpatterns = router.urls
