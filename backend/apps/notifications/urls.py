"""API routes for the Notifications module.

Mounted under `/api/v1/notifications/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "notifications"

router = DefaultRouter()

urlpatterns = router.urls
