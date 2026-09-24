"""Identity domain models.

Owns the user account, credentials, verification/reset tokens, MFA devices,
tracked sessions and the login-attempt ledger. Authorization primitives
(roles, permissions, scoped assignments) live in ``apps.security``.

Design notes
------------
* Email is the unique login identifier (case-insensitive).
* The user's home organization is optional: platform administrators belong to
  no single organization, everyone else belongs to exactly one.
* Tokens are stored **hashed** (SHA-256); the raw value only ever exists in the
  email that carries it, never in the database or logs.
* MFA secrets are encrypted at rest with a key derived from ``SECRET_KEY``.
"""
from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

PHONE_VALIDATOR = RegexValidator(
    regex=r"^\+?[0-9 ()\-]{7,20}$",
    message=_("Enter a valid phone number (digits, spaces, dashes, optional + prefix)."),
)


def generate_reference(prefix: str) -> str:
    """Human-friendly, unguessable public identifier (e.g. ``USR-4f2c1a9b``)."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def default_user_reference() -> str:
    """Module-level default so it can be serialised into migrations."""
    return generate_reference("USR")


class UserManager(BaseUserManager):
    """Manager for the email-based custom user model."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        requested_must_change = extra_fields.get("must_change_password")
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        # ``set_password()`` clears the flag (a *user-chosen* password never
        # forces a change), so an administrator-issued temporary password must
        # be recorded again here.
        if requested_must_change:
            user.must_change_password = True
        user.full_clean(exclude=["password", "last_login"])
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        user = self._create_user(email, password, **extra_fields)
        # Platform administrators are trusted identities: no organisation
        # scoping, email pre-verified, MFA enforced by policy.
        user.email_verified_at = user.email_verified_at or timezone.now()
        user.save(update_fields=["email_verified_at"])
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """Application user.

    Authentication is password-based (Argon2id) with optional TOTP MFA.
    Authorization is *not* stored here — it is derived from scoped role
    assignments in ``apps.security`` (see ``docs/rbac.md``).
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INVITED = "invited", _("Invited")
        SUSPENDED = "suspended", _("Suspended")
        DEACTIVATED = "deactivated", _("Deactivated")

    # --- Identity ---------------------------------------------------------
    reference = models.CharField(
        max_length=32, unique=True, default=default_user_reference, editable=False
    )
    email = models.EmailField(_("email address"), unique=True, db_index=True)
    first_name = models.CharField(_("first name"), max_length=150)
    last_name = models.CharField(_("last name"), max_length=150)
    phone = models.CharField(
        _("phone"), max_length=32, blank=True, default="", validators=[PHONE_VALIDATOR]
    )
    job_title = models.CharField(_("job title"), max_length=150, blank=True, default="")
    timezone = models.CharField(max_length=64, blank=True, default="UTC")
    locale = models.CharField(max_length=16, blank=True, default="en")

    # --- Tenancy ----------------------------------------------------------
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
        help_text=_("Home organisation. Empty for platform administrators."),
    )

    # --- Status / lifecycle ----------------------------------------------
    is_active = models.BooleanField(
        default=True,
        help_text=_("Unchecked accounts cannot authenticate (soft deactivation)."),
    )
    is_staff = models.BooleanField(
        default=False, help_text=_("May sign in to the Django admin site.")
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    is_email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivation_reason = models.CharField(max_length=255, blank=True, default="")

    # --- Verification / MFA policy ---------------------------------------
    mfa_required = models.BooleanField(
        default=False, help_text=_("Account policy: MFA enrolment is mandatory.")
    )
    must_change_password = models.BooleanField(
        default=False, help_text=_("Set when an administrator issues a temporary password.")
    )

    # --- Login state & lockout -------------------------------------------
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    failed_login_count = models.PositiveIntegerField(default=0)
    last_failed_login_at = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)

    # --- Timestamps -------------------------------------------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["first_name", "last_name", "email"]
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower().strip()
        super().save(*args, **kwargs)

    # --- Presentation -----------------------------------------------------
    @property
    def full_name(self) -> str:
        return (f"{self.first_name} {self.last_name}").strip() or self.email

    @property
    def short_name(self) -> str:
        return self.first_name or self.email.split("@")[0]

    @property
    def is_platform_admin(self) -> bool:
        """Platform-wide administrator (sees every organization)."""
        return bool(self.is_superuser and self.is_active)

    # --- Login / lockout state -------------------------------------------
    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    @property
    def is_email_usable(self) -> bool:
        return self.is_active and self.status != self.Status.DEACTIVATED

    @property
    def has_mfa_enabled(self) -> bool:
        return self.mfa_devices.filter(confirmed_at__isnull=False).exists()

    def lock_for(self, seconds: int) -> None:
        self.locked_until = timezone.now() + timezone.timedelta(seconds=seconds)

    def clear_lock(self) -> None:
        self.locked_until = None
        self.failed_login_count = 0

    def mark_email_verified(self) -> None:
        self.is_email_verified = True
        self.email_verified_at = timezone.now()

    def set_password(self, raw_password, *, record_change: bool = True):
        super().set_password(raw_password)
        if record_change:
            self.password_changed_at = timezone.now()
            self.must_change_password = False

    # --- Authorization helpers -------------------------------------------
    def highest_role_level(self, organization=None) -> int:
        """Authority rank of the strongest role held (100 for platform admins)."""
        if self.is_superuser:
            return 100
        from apps.security.models import RoleAssignment

        qs = RoleAssignment.objects.filter(
            user=self, is_active=True, role__is_active=True
        ).select_related("role")
        if organization is not None:
            qs = qs.filter(models.Q(organization=organization) | models.Q(organization__isnull=True))
        return max((assignment.role.level for assignment in qs), default=0)

    def has_permission(self, codename: str, *, organization=None, warehouse=None) -> bool:
        """Scoped permission check — the only supported authorization entry point."""
        from apps.security.authorization import AuthorizationService

        return AuthorizationService(self).has_permission(
            codename, organization=organization, warehouse=warehouse
        )


class TokenPurpose(models.TextChoices):
    EMAIL_VERIFICATION = "email_verification", _("Email verification")
    PASSWORD_RESET = "password_reset", _("Password reset")


class OneTimeToken(models.Model):
    """Hashed, single-use, expiring token (email verification / password reset).

    The raw token is returned once by the issuing service and never stored.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tokens")
    purpose = models.CharField(max_length=32, choices=TokenPurpose.choices)
    token_hash = models.CharField(max_length=64, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    requested_ip = models.GenericIPAddressField(null=True, blank=True)
    requested_user_agent = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = _("one-time token")
        verbose_name_plural = _("one-time tokens")
        indexes = [models.Index(fields=["user", "purpose", "used_at"])]

    def __str__(self) -> str:
        return f"{self.purpose} for {self.user_id}"

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    @property
    def is_usable(self) -> bool:
        return self.used_at is None and not self.is_expired


class MFADevice(models.Model):
    """A TOTP authenticator device (architecture supports several per user)."""

    class DeviceType(models.TextChoices):
        TOTP = "totp", _("Authenticator app (TOTP)")
        RECOVERY = "recovery", _("Recovery codes")

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_devices")
    name = models.CharField(max_length=64, default="Authenticator app")
    device_type = models.CharField(
        max_length=16, choices=DeviceType.choices, default=DeviceType.TOTP
    )
    secret_encrypted = models.TextField(blank=True, default="")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("MFA device")
        verbose_name_plural = _("MFA devices")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.user_id})"

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None


class MFARecoveryCode(models.Model):
    """Single-use recovery code, stored as a password hash."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recovery_codes")
    code_hash = models.CharField(max_length=255)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("MFA recovery code")
        verbose_name_plural = _("MFA recovery codes")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"recovery code for user {self.user_id}"

    @property
    def is_used(self) -> bool:
        return self.used_at is not None


class LoginAttempt(models.Model):
    """Audit ledger of authentication attempts (success and failure)."""

    class Result(models.TextChoices):
        SUCCESS = "success", _("Success")
        INVALID_CREDENTIALS = "invalid_credentials", _("Invalid credentials")
        LOCKED = "locked", _("Account locked")
        INACTIVE = "inactive", _("Account inactive")
        UNVERIFIED_EMAIL = "unverified_email", _("Email not verified")
        MFA_REQUIRED = "mfa_required", _("MFA challenge issued")
        MFA_FAILED = "mfa_failed", _("MFA verification failed")
        MFA_PASSED = "mfa_passed", _("MFA verification passed")
        THROTTLED = "throttled", _("Rate limited")

    email_attempted = models.CharField(max_length=254, db_index=True)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="login_attempts"
    )
    result = models.CharField(max_length=32, choices=Result.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    request_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("login attempt")
        verbose_name_plural = _("login attempts")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email_attempted", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.email_attempted} → {self.result}"


class UserSession(models.Model):
    """Tracked authentication session bound to a Django session key.

    Enables "active sessions" listings, remote revocation and idle expiry —
    Django's session table alone cannot express any of that.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    session_key = models.CharField(max_length=64, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    device_label = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=64, blank=True, default="")
    mfa_verified = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("user session")
        verbose_name_plural = _("user sessions")
        ordering = ["-last_seen_at"]
        indexes = [models.Index(fields=["user", "revoked_at"])]

    def __str__(self) -> str:
        return f"session {self.session_key[:8]}… for {self.user_id}"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()

    def revoke(self, reason: str = "revoked") -> None:
        self.revoked_at = timezone.now()
        self.revoked_reason = reason
        self.save(update_fields=["revoked_at", "revoked_reason"])
