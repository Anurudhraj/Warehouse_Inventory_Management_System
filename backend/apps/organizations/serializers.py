"""Serializers for organizations and branches."""
from __future__ import annotations

from rest_framework import serializers

from apps.organizations.models import Branch, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    branch_count = serializers.SerializerMethodField()
    warehouse_count = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "code",
            "name",
            "slug",
            "legal_name",
            "tax_id",
            "status",
            "is_active",
            "contact_email",
            "contact_phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "default_currency",
            "timezone",
            "locale",
            "settings",
            "branch_count",
            "warehouse_count",
            "user_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_branch_count(self, obj) -> int:
        return getattr(obj, "branch_total", None) or obj.branches.count()

    def get_warehouse_count(self, obj) -> int:
        annotated = getattr(obj, "warehouse_total", None)
        if annotated is not None:
            return annotated
        from apps.warehouses.models import Warehouse

        return Warehouse.objects.filter(branch__organization=obj).count()

    def get_user_count(self, obj) -> int:
        return getattr(obj, "user_total", None) or obj.users.count()


class OrganizationSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "code", "name", "status", "is_active", "default_currency", "timezone"]
        read_only_fields = fields


class BranchSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_code = serializers.CharField(source="organization.code", read_only=True)
    manager_name = serializers.CharField(source="manager.full_name", read_only=True, default=None)
    warehouse_count = serializers.SerializerMethodField()
    effective_timezone = serializers.CharField(read_only=True)

    class Meta:
        model = Branch
        fields = [
            "id",
            "organization",
            "organization_name",
            "organization_code",
            "code",
            "name",
            "branch_type",
            "is_active",
            "manager",
            "manager_name",
            "contact_email",
            "contact_phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "timezone",
            "effective_timezone",
            "notes",
            "warehouse_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "warehouse_count", "effective_timezone"]

    def get_warehouse_count(self, obj) -> int:
        annotated = getattr(obj, "warehouse_total", None)
        if isinstance(annotated, int):
            return annotated
        return obj.warehouses.count()

    def validate(self, attrs):
        organization = attrs.get("organization") or getattr(self.instance, "organization", None)
        manager = attrs.get("manager")
        if manager is not None and organization is not None and manager.organization_id:
            if manager.organization_id != organization.id:
                raise serializers.ValidationError(
                    {"manager": ["The manager must belong to the same organization."]}
                )
        return attrs


class BranchSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "organization", "code", "name", "branch_type", "is_active", "city"]
        read_only_fields = fields
