"""Serializers for the RBAC API (roles, permissions, assignments)."""
from __future__ import annotations

from rest_framework import serializers

from apps.security.models import Permission, Role, RoleAssignment
from apps.security.permission_registry import is_registered


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "codename", "name", "module", "description", "is_sensitive"]
        read_only_fields = fields


class RoleSerializer(serializers.ModelSerializer):
    permission_codes = serializers.SerializerMethodField()
    permission_count = serializers.SerializerMethodField()
    assignment_count = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.name", read_only=True, default=None)
    modules = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            "id",
            "code",
            "name",
            "description",
            "level",
            "is_system",
            "is_platform",
            "is_active",
            "organization",
            "organization_name",
            "permission_codes",
            "permission_count",
            "assignment_count",
            "modules",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "is_system",
            "is_platform",
            "organization",
            "permission_codes",
            "permission_count",
            "assignment_count",
            "modules",
            "created_at",
            "updated_at",
        ]

    def get_permission_codes(self, obj) -> list[str]:
        codes = getattr(obj, "_permission_codes_cache", None)
        if codes is None:
            codes = sorted(obj.permissions.values_list("codename", flat=True))
        return codes

    def get_permission_count(self, obj) -> int:
        return len(self.get_permission_codes(obj))

    def get_assignment_count(self, obj) -> int:
        annotated = getattr(obj, "assignment_total", None)
        return annotated if annotated is not None else obj.assignments.count()

    def get_modules(self, obj) -> list[str]:
        return sorted({code.split(".", 1)[0] for code in self.get_permission_codes(obj)})


class RoleCreateSerializer(serializers.ModelSerializer):
    """Organization-scoped custom roles (system roles are immutable)."""

    permission_codes = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "level", "permission_codes"]
        read_only_fields = ["id"]

    def validate_code(self, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
        if not normalized.replace("_", "").isalnum():
            raise serializers.ValidationError("Use letters, numbers and underscores only.")
        return normalized

    def validate_permission_codes(self, value: list[str]) -> list[str]:
        unknown = [code for code in value if not is_registered(code)]
        if unknown:
            raise serializers.ValidationError(f"Unknown permission(s): {', '.join(sorted(unknown))}")
        return value

    def validate_level(self, value: int) -> int:
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Level must be between 0 and 100.")
        return value


class RolePermissionUpdateSerializer(serializers.Serializer):
    permission_codes = serializers.ListField(child=serializers.CharField(), allow_empty=True)

    def validate_permission_codes(self, value: list[str]) -> list[str]:
        unknown = [code for code in value if not is_registered(code)]
        if unknown:
            raise serializers.ValidationError(f"Unknown permission(s): {', '.join(sorted(unknown))}")
        return value


class RoleAssignmentSerializer(serializers.ModelSerializer):
    role_code = serializers.CharField(source="role.code", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    role_level = serializers.IntegerField(source="role.level", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True, default=None)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default=None)
    scope = serializers.CharField(read_only=True)
    is_effective = serializers.BooleanField(read_only=True)

    class Meta:
        model = RoleAssignment
        fields = [
            "id",
            "user",
            "user_email",
            "user_name",
            "role",
            "role_code",
            "role_name",
            "role_level",
            "organization",
            "organization_name",
            "warehouse",
            "warehouse_name",
            "scope",
            "is_active",
            "is_effective",
            "expires_at",
            "granted_by",
            "granted_at",
            "note",
        ]
        read_only_fields = [
            "id",
            "user_email",
            "user_name",
            "role_code",
            "role_name",
            "role_level",
            "organization_name",
            "warehouse_name",
            "scope",
            "is_effective",
            "granted_by",
            "granted_at",
        ]


class RoleAssignmentCreateSerializer(serializers.Serializer):
    user = serializers.IntegerField()
    role = serializers.IntegerField()
    organization = serializers.IntegerField(required=False, allow_null=True)
    warehouse = serializers.IntegerField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class EffectivePermissionSerializer(serializers.Serializer):
    """Response for ``GET /security/me/permissions/`` (drives the frontend)."""

    permissions = serializers.ListField(child=serializers.CharField())
    organizations = serializers.ListField(child=serializers.IntegerField(), required=False)
    warehouses = serializers.ListField(child=serializers.IntegerField(), required=False)
    is_platform_admin = serializers.BooleanField()
    roles = serializers.ListField(child=serializers.DictField(), required=False)
