"""Admin registrations for warehouse master data."""
from django.contrib import admin

from apps.warehouses.models import Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "branch", "warehouse_type", "is_active", "city")
    list_filter = ("warehouse_type", "is_active", "branch__organization")
    search_fields = ("code", "name", "city")
    autocomplete_fields = ("branch", "manager")
    readonly_fields = ("created_at", "updated_at")
