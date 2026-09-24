"""Admin registrations for organizations and branches."""
from django.contrib import admin

from apps.organizations.models import Branch, Organization


class BranchInline(admin.TabularInline):
    model = Branch
    extra = 0
    fields = ("code", "name", "branch_type", "is_active", "city", "manager")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "status", "is_active", "default_currency", "timezone")
    list_filter = ("status", "is_active", "country")
    search_fields = ("code", "name", "legal_name", "tax_id")
    readonly_fields = ("slug", "created_at", "updated_at")
    inlines = [BranchInline]


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "branch_type", "is_active", "city")
    list_filter = ("branch_type", "is_active", "organization")
    search_fields = ("code", "name", "city")
    autocomplete_fields = ("organization", "manager")
