"""Admin registrations for identity models."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.identity.models import (
    LoginAttempt,
    MFADevice,
    MFARecoveryCode,
    OneTimeToken,
    User,
    UserSession,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Django admin for the email-based user model."""

    ordering = ("email",)
    list_display = (
        "email",
        "full_name",
        "organization",
        "status",
        "is_active",
        "is_staff",
        "is_email_verified",
        "last_login_at",
    )
    list_filter = ("status", "is_active", "is_staff", "is_superuser", "is_email_verified", "organization")
    search_fields = ("email", "first_name", "last_name", "reference")
    readonly_fields = (
        "reference",
        "last_login_at",
        "last_login_ip",
        "last_failed_login_at",
        "failed_login_count",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal information", {"fields": ("first_name", "last_name", "phone", "job_title")}),
        ("Organization", {"fields": ("organization", "timezone", "locale")}),
        ("Status", {"fields": ("status", "is_active", "is_staff", "is_superuser", "deactivated_at", "deactivation_reason")}),
        ("Verification & MFA", {"fields": ("is_email_verified", "email_verified_at", "mfa_required")}),
        (
            "Security metadata",
            {
                "fields": (
                    "reference",
                    "last_login_at",
                    "last_login_ip",
                    "last_failed_login_at",
                    "failed_login_count",
                    "locked_until",
                    "password_changed_at",
                    "must_change_password",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "organization",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "device_label", "ip_address", "created_at", "last_seen_at", "revoked_at")
    list_filter = ("revoked_reason", "mfa_verified")
    search_fields = ("user__email", "ip_address")
    readonly_fields = ("session_key", "created_at", "last_seen_at")


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("email_attempted", "result", "ip_address", "created_at")
    list_filter = ("result",)
    search_fields = ("email_attempted", "ip_address")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MFADevice)
class MFADeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "device_type", "confirmed_at", "last_used_at")
    search_fields = ("user__email",)
    exclude = ("secret_encrypted",)  # never expose secrets through the admin


@admin.register(MFARecoveryCode)
class MFARecoveryCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "used_at", "created_at")
    search_fields = ("user__email",)
    exclude = ("code_hash",)

    def has_add_permission(self, request):
        return False


@admin.register(OneTimeToken)
class OneTimeTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "expires_at", "used_at", "created_at")
    list_filter = ("purpose",)
    search_fields = ("user__email",)
    exclude = ("token_hash",)

    def has_add_permission(self, request):
        return False
