"""Serializers for warehouse master data (foundation)."""
from __future__ import annotations

from rest_framework import serializers

from apps.warehouses.models import Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    branch_code = serializers.CharField(source="branch.code", read_only=True)
    organization = serializers.IntegerField(source="branch.organization_id", read_only=True)
    organization_name = serializers.CharField(source="branch.organization.name", read_only=True)
    manager_name = serializers.CharField(source="manager.full_name", read_only=True, default=None)
    effective_timezone = serializers.CharField(read_only=True)

    class Meta:
        model = Warehouse
        fields = [
            "id",
            "code",
            "name",
            "warehouse_type",
            "is_active",
            "branch",
            "branch_name",
            "branch_code",
            "organization",
            "organization_name",
            "manager",
            "manager_name",
            "address_line1",
            "city",
            "state",
            "postal_code",
            "country",
            "timezone",
            "effective_timezone",
            "settings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "effective_timezone"]


class WarehouseSummarySerializer(serializers.ModelSerializer):
    organization = serializers.IntegerField(source="branch.organization_id", read_only=True)

    class Meta:
        model = Warehouse
        fields = ["id", "code", "name", "warehouse_type", "is_active", "branch", "organization"]
        read_only_fields = fields
