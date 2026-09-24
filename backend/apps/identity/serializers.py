"""Serializers for the identity API.

Serializers shape and validate input; authorization decisions belong to the
service layer and the permission classes. Anything sensitive (password hashes,
tokens, MFA secrets) is write-only or excluded entirely.
"""
from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.identity.models import LoginAttempt, MFADevice, User, UserSession
from apps.identity.services import normalize_email
from apps.security.authorization import AuthorizationService
from apps.security.models import RoleAssignment


class OrganizationBriefSerializer(serializers.Serializer):
    """Contract for the nested organization summary (implemented by the
    organizations app to avoid a circular import at module load time)."""

    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class CaseInsensitiveEmailField(serializers.EmailField):
    def to_internal_value(self, data):
        return normalize_email(super().to_internal_value(data))


class UserSerializer(serializers.ModelSerializer):
    """Full user representation returned to administrators."""

    full_name = serializers.CharField(read_only=True)
    organization = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    has_mfa_enabled = serializers.BooleanField(read_only=True)
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "reference",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "job_title",
            "timezone",
            "locale",
            "organization",
            "status",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_email_verified",
            "email_verified_at",
            "mfa_required",
            "has_mfa_enabled",
            "must_change_password",
            "is_locked",
            "locked_until",
            "failed_login_count",
            "last_login_at",
            "last_login_ip",
            "password_changed_at",
            "roles",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reference",
            "is_staff",
            "is_superuser",
            "is_email_verified",
            "email_verified_at",
            "must_change_password",
            "locked_until",
            "failed_login_count",
            "last_login_at",
            "last_login_ip",
            "password_changed_at",
            "created_at",
            "updated_at",
        ]

    def get_organization(self, obj):
        if not obj.organization:
            return None
        return {
            "id": obj.organization.id,
            "code": obj.organization.code,
            "name": obj.organization.name,
        }

    def get_roles(self, obj) -> list[dict]:
        """Effective role assignments, annotated for the UI."""
        assignments = getattr(obj, "prefetched_assignments", None)
        if assignments is None:
            assignments = (
                RoleAssignment.objects.filter(user=obj, is_active=True)
                .select_related("role", "organization", "warehouse")
                .order_by("-role__level")
            )
        return [
            {
                "id": assignment.id,
                "role": assignment.role.code,
                "role_name": assignment.role.name,
                "level": assignment.role.level,
                "organization_id": assignment.organization_id,
                "warehouse_id": assignment.warehouse_id,
                "scope": assignment.scope_label,
                "expires_at": assignment.expires_at,
            }
            for assignment in assignments
            if assignment.is_effective or assignment.is_active
        ]


class UserSummarySerializer(serializers.ModelSerializer):
    """Compact representation for lists, pickers and lookups."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "reference",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "job_title",
            "status",
            "is_active",
            "organization",
            "last_login_at",
        ]
        read_only_fields = fields


class ProfileSerializer(serializers.ModelSerializer):
    """Self-service profile: users may edit their own presentation data only."""

    organization = serializers.SerializerMethodField()
    has_mfa_enabled = serializers.BooleanField(read_only=True)
    effective_permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "reference",
            "email",
            "first_name",
            "last_name",
            "phone",
            "job_title",
            "timezone",
            "locale",
            "organization",
            "status",
            "is_email_verified",
            "mfa_required",
            "has_mfa_enabled",
            "must_change_password",
            "last_login_at",
            "password_changed_at",
            "effective_permissions",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "reference",
            "email",
            "organization",
            "status",
            "is_email_verified",
            "mfa_required",
            "has_mfa_enabled",
            "must_change_password",
            "last_login_at",
            "password_changed_at",
            "effective_permissions",
            "created_at",
        ]

    def get_organization(self, obj):
        if not obj.organization:
            return None
        return {
            "id": obj.organization.id,
            "code": obj.organization.code,
            "name": obj.organization.name,
        }

    def get_effective_permissions(self, obj) -> list[str]:
        request = self.context.get("request")
        if request is None:
            return []
        service = AuthorizationService(obj)
        return sorted(service.effective_permission_codes())


class UserCreateSerializer(serializers.Serializer):
    """Administrator-driven user creation (optionally with a temporary password)."""

    email = CaseInsensitiveEmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    job_title = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    organization_id = serializers.IntegerField(required=False, allow_null=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        min_length=12,
        help_text="Optional temporary password. When omitted the user is invited by email.",
    )
    mfa_required = serializers.BooleanField(required=False, default=False)
    send_verification_email = serializers.BooleanField(required=False, default=True)

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class UserUpdateSerializer(serializers.ModelSerializer):
    """Administrator edits (no credential or platform-flag changes here)."""

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "phone",
            "job_title",
            "timezone",
            "locale",
            "organization",
            "status",
            "mfa_required",
        ]

    def validate_status(self, value: str) -> str:
        if value == User.Status.DEACTIVATED:
            raise serializers.ValidationError(
                "Use the deactivate endpoint so sessions are revoked."
            )
        return value


class SetPasswordSerializer(serializers.Serializer):
    """Administrator password reset for a user (temporary password policy)."""

    password = serializers.CharField(write_only=True, min_length=12)
    must_change_password = serializers.BooleanField(required=False, default=True)

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class DeactivateUserSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
class LoginSerializer(serializers.Serializer):
    email = CaseInsensitiveEmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class LoginResponseSerializer(serializers.Serializer):
    mfa_required = serializers.BooleanField()
    challenge_token = serializers.CharField(allow_null=True, required=False)
    user = ProfileSerializer(read_only=True)
    permissions = serializers.ListField(child=serializers.CharField(), required=False)


class MFAChallengeSerializer(serializers.Serializer):
    challenge_token = serializers.CharField()
    code = serializers.CharField(max_length=16)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=12)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = CaseInsensitiveEmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=12)


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField()


# ---------------------------------------------------------------------------
# Sessions & MFA
# ---------------------------------------------------------------------------
class UserSessionSerializer(serializers.ModelSerializer):
    is_current = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserSession
        fields = [
            "id",
            "session_key",
            "ip_address",
            "user_agent",
            "device_label",
            "created_at",
            "last_seen_at",
            "expires_at",
            "revoked_at",
            "revoked_reason",
            "mfa_verified",
            "is_current",
            "is_active",
        ]
        read_only_fields = fields

    def get_is_current(self, obj) -> bool:
        request = self.context.get("request")
        if request is None or not request.session.session_key:
            return False
        return obj.session_key == request.session.session_key


class MFADeviceSerializer(serializers.ModelSerializer):
    is_confirmed = serializers.BooleanField(read_only=True)

    class Meta:
        model = MFADevice
        fields = ["id", "name", "device_type", "is_confirmed", "confirmed_at", "last_used_at", "created_at"]
        read_only_fields = fields


class MFAEnrolmentSerializer(serializers.Serializer):
    """Returned once, at enrolment time: the secret must not be re-readable."""

    secret = serializers.CharField(read_only=True)
    otpauth_uri = serializers.CharField(read_only=True)
    device = MFADeviceSerializer(read_only=True)


class MFAConfirmSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=16)


class MFADisableSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)


class MFARecoveryCodesSerializer(serializers.Serializer):
    codes = serializers.ListField(child=serializers.CharField(), read_only=True)


class LoginAttemptSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default=None)

    class Meta:
        model = LoginAttempt
        fields = [
            "id",
            "email_attempted",
            "user_email",
            "result",
            "ip_address",
            "user_agent",
            "request_id",
            "created_at",
        ]
        read_only_fields = fields
