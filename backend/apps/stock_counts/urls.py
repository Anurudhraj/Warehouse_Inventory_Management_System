"""API routes for the Stock Counts module.

Mounted under `/api/v1/stock_counts/`. Register viewsets on `router` as the
module is implemented in later parts of the build plan.
"""

from rest_framework.routers import DefaultRouter

app_name = "stock_counts"

router = DefaultRouter()

urlpatterns = router.urls
