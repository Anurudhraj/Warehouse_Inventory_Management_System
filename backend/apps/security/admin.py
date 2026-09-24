"""Admin registrations for RBAC models."""
from django.contrib import admin

from apps.security.models import Permission, Role, RoleAssignment


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("codename", "name", "module", "is_sensitive")
    list_filter = ("module", "is_sensitive")
    search_fields = ("codename", "name")
    readonly_fields = ("created_at",)
    ordering = ("module", "codename")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "level", "is_system", "is_platform", "is_active", "organization")
    list_filter = ("is_system", "is_platform", "is_active", "organization")
    search_fields = ("code", "name")
    filter_horizontal = ("permissions",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "organization", "warehouse", "is_active", "granted_at", "expires_at")
    list_filter = ("is_active", "role", "organization")
    search_fields = ("user__email", "role__code")
    autocomplete_fields = ("user",)
    readonly_fields = ("granted_at",)
