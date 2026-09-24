"""Warehouse routes — mounted at ``/api/v1/warehouses/``."""
from rest_framework.routers import DefaultRouter

from apps.warehouses.views import WarehouseViewSet

app_name = "warehouses"

router = DefaultRouter()
router.register("", WarehouseViewSet, basename="warehouse")

urlpatterns = router.urls
