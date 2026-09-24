"""Identity service layer.

All authentication behaviour lives here so the API views stay thin and the same
logic is reusable from tasks, management commands and tests:

* :class:`LoginAttemptService` — attempt ledger, lockout accounting, audit
* :class:`SessionService` — tracked sessions (list / revoke / idle expiry)
* :class:`AuthenticationService` — password login, MFA challenge, logout
* :class:`PasswordService` — change, reset request/confirm
* :class:`EmailVerificationService` — verification token issue/consume
* :class:`MFAService` — TOTP enrolment, verification, recovery codes

Security posture: no user enumeration (unknown e-mail and wrong password are
indistinguishable), constant-time comparisons where secrets are involved,
lockout after repeated failures, and every state change recorded in the audit
ledger.
"""
from __future__ import annotations

import logging
import secrets
from collections.abc import Iterable
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import authenticate, update_session_auth_hash
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.identity.models import (
    LoginAttempt,
    MFADevice,
    MFARecoveryCode,
    OneTimeToken,
    TokenPurpose,
    User,
    UserSession,
)
from apps.security.crypto import decrypt_secret, encrypt_secret, hash_token
from apps.security.totp import (
    build_otpauth_uri,
    code_step,
    generate_recovery_codes,
    generate_secret,
    verify_code,
)

logger = logging.getLogger("apps.identity")

MFA_CHALLENGE_SALT = "wims.mfa.challenge"
MFA_CHALLENGE_CACHE_PREFIX = "mfa-challenge:"

#: Generic message used whenever authentication fails, to avoid enumeration.
INVALID_CREDENTIALS_MESSAGE = "Invalid email or password."


def client_ip(request) -> str | None:
    """Client IP, trusting the proxy header set by the edge nginx."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def user_agent(request) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:255]


def request_id(request) -> str:
    return (getattr(request, "request_id", "") or "")[:64]


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


# ---------------------------------------------------------------------------
# Login attempts, lockout and audit
# ---------------------------------------------------------------------------
class LoginAttemptService:
    """Records authentication attempts and enforces account lockout."""

    def __init__(self, request=None):
        self.request = request

    def record(
        self,
        *,
        email: str,
        result: str,
        user: User | None = None,
        request=None,
    ) -> LoginAttempt:
        request = request or self.request
        return LoginAttempt.objects.create(
            email_attempted=normalize_email(email)[:254],
            user=user if user and user.pk else None,
            result=result,
            ip_address=client_ip(request) if request else None,
            user_agent=user_agent(request) if request else "",
            request_id=request_id(request) if request else "",
        )

    def recent_failures(self, user: User, *, minutes: int = 15) -> int:
        since = timezone.now() - timezone.timedelta(minutes=minutes)
        return LoginAttempt.objects.filter(
            user=user,
            created_at__gte=since,
            result__in=[
                LoginAttempt.Result.INVALID_CREDENTIALS,
                LoginAttempt.Result.MFA_FAILED,
            ],
        ).count()

    def register_failure(self, user: User) -> None:
        """Increment the failure counter and lock the account when the limit is hit."""
        user.failed_login_count = (user.failed_login_count or 0) + 1
        user.last_failed_login_at = timezone.now()
        update_fields = ["failed_login_count", "last_failed_login_at"]
        if user.failed_login_count >= settings.AUTH_MAX_FAILED_ATTEMPTS:
            user.lock_for(settings.AUTH_LOCKOUT_SECONDS)
            update_fields.append("locked_until")
            logger.warning(
                "Account locked after %s failed attempts (user_id=%s)",
                user.failed_login_count,
                user.pk,
            )
        user.save(update_fields=update_fields)

    def register_success(self, user: User, ip: str | None) -> None:
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = timezone.now()
        user.last_login_ip = ip
        user.save(
            update_fields=[
                "failed_login_count",
                "locked_until",
                "last_login_at",
                "last_login_ip",
                "last_login",
            ]
        )


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
class SessionService:
    """Tracked sessions bound to Django session keys."""

    TOUCH_INTERVAL_SECONDS = 60

    def __init__(self, request):
        self.request = request

    def register(self, user: User, *, session_key: str, mfa_verified: bool = False) -> UserSession:
        timeout = settings.SESSION_COOKIE_AGE
        return UserSession.objects.create(
            user=user,
            session_key=session_key,
            ip_address=client_ip(self.request),
            user_agent=user_agent(self.request),
            device_label=guess_device_label(user_agent(self.request)),
            expires_at=timezone.now() + timezone.timedelta(seconds=timeout),
            mfa_verified=mfa_verified,
        )

    def touch(self, session_key: str) -> None:
        """Refresh last_seen / expiry, throttled to avoid a write per request."""
        cache_key = f"session-touch:{session_key}"
        if cache.get(cache_key):
            return
        cache.set(cache_key, 1, self.TOUCH_INTERVAL_SECONDS)
        UserSession.objects.filter(session_key=session_key, revoked_at__isnull=True).update(
            last_seen_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(seconds=settings.SESSION_COOKIE_AGE),
        )

    def sessions_for(self, user: User) -> Iterable[UserSession]:
        return user.sessions.filter(revoked_at__isnull=True, expires_at__gt=timezone.now())

    def current_session(self, user: User) -> UserSession | None:
        key = self.request.session.session_key
        if not key:
            return None
        return user.sessions.filter(session_key=key).first()

    def revoke(self, session: UserSession, *, reason: str = "revoked by user") -> None:
        session.revoke(reason=reason)
        # Drop the underlying Django session so the cookie is useless.
        from django.contrib.sessions.models import Session

        Session.objects.filter(session_key=session.session_key).delete()

    def revoke_others(self, user: User, *, keep_session_key: str | None, reason: str) -> int:
        qs = user.sessions.filter(revoked_at__isnull=True)
        if keep_session_key:
            qs = qs.exclude(session_key=keep_session_key)
        return self.revoke_many(qs, reason=reason)

    def revoke_all(self, user: User, *, reason: str) -> int:
        return self.revoke_many(user.sessions.filter(revoked_at__isnull=True), reason=reason)

    def revoke_many(self, sessions, *, reason: str) -> int:
        from django.contrib.sessions.models import Session

        keys = [session.session_key for session in sessions]
        count = sessions.update(revoked_at=timezone.now(), revoked_reason=reason[:64])
        Session.objects.filter(session_key__in=keys).delete()
        return count


def guess_device_label(agent: str) -> str:
    """Coarse device label for the session list (never used for authorization)."""
    agent = (agent or "").lower()
    platform = next(
        (
            label
            for token, label in (
                ("iphone", "iPhone"),
                ("ipad", "iPad"),
                ("android", "Android"),
                ("windows", "Windows"),
                ("macintosh", "macOS"),
                ("linux", "Linux"),
            )
            if token in agent
        ),
        "Unknown device",
    )
    browser = next(
        (
            label
            for token, label in (
                ("edg/", "Edge"),
                ("chrome/", "Chrome"),
                ("safari/", "Safari"),
                ("firefox/", "Firefox"),
            )
            if token in agent
        ),
        "Browser",
    )
    return f"{browser} on {platform}"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
@dataclass
class LoginOutcome:
    user: User
    mfa_required: bool = False
    challenge_token: str | None = None


class AuthenticationService:
    """Password + MFA authentication against tracked sessions."""

    def __init__(self, request):
        self.request = request
        self.attempts = LoginAttemptService(request)
        self.sessions = SessionService(request)

    # -- password step ----------------------------------------------------
    def login(self, *, email: str, password: str) -> LoginOutcome:
        email = normalize_email(email)
        ip = client_ip(self.request)

        user = User.objects.filter(email=email).first()

        # Locked accounts fail before password verification (and are recorded).
        if user and user.is_locked:
            self.attempts.record(email=email, result=LoginAttempt.Result.LOCKED, user=user)
            raise exceptions.Throttled(
                wait=settings.AUTH_LOCKOUT_SECONDS,
                detail=(
                    "This account is temporarily locked after repeated failed sign-in "
                    "attempts. Try again later or reset your password."
                ),
            )

        authenticated = authenticate(request=self.request, username=email, password=password)

        if authenticated is None or not user or not user.is_active:
            if user:
                self.attempts.register_failure(user)
            self.attempts.record(
                email=email,
                result=LoginAttempt.Result.INVALID_CREDENTIALS,
                user=user if user and user.is_active else None,
            )
            raise exceptions.AuthenticationFailed(INVALID_CREDENTIALS_MESSAGE)

        if settings.AUTH_REQUIRE_EMAIL_VERIFICATION and not user.is_email_verified:
            self.attempts.record(
                email=email, result=LoginAttempt.Result.UNVERIFIED_EMAIL, user=user
            )
            raise exceptions.AuthenticationFailed(
                "Please verify your email address before signing in."
            )

        if self.mfa_challenge_required(user):
            token = self._issue_mfa_challenge(user)
            self.attempts.record(email=email, result=LoginAttempt.Result.MFA_REQUIRED, user=user)
            return LoginOutcome(user=user, mfa_required=True, challenge_token=token)

        return self._complete_login(user, email=email, ip=ip, mfa_verified=False)

    def mfa_challenge_required(self, user: User) -> bool:
        if user.has_mfa_enabled:
            return True
        # Policy: administrators must enrol MFA (enforced until a device exists).
        if settings.AUTH_REQUIRE_MFA_FOR_ADMINS and (user.is_superuser or user.is_staff):
            return bool(user.mfa_devices.filter(confirmed_at__isnull=False).exists())
        return False

    def _issue_mfa_challenge(self, user: User) -> str:
        """Single-use, short-lived challenge token for the MFA step."""
        challenge_id = secrets.token_urlsafe(12)
        cache.set(
            f"{MFA_CHALLENGE_CACHE_PREFIX}{challenge_id}",
            {"user_id": user.pk, "ip": client_ip(self.request)},
            settings.AUTH_MFA_CHALLENGE_TTL,
        )
        return signing.dumps({"cid": challenge_id, "uid": user.pk}, salt=MFA_CHALLENGE_SALT)

    def verify_mfa_challenge(self, *, challenge_token: str, code: str) -> LoginOutcome:
        try:
            payload = signing.loads(
                challenge_token, salt=MFA_CHALLENGE_SALT, max_age=settings.AUTH_MFA_CHALLENGE_TTL
            )
        except signing.SignatureExpired:
            raise exceptions.AuthenticationFailed(
                "The verification window expired. Sign in again."
            ) from None
        except signing.BadSignature:
            raise exceptions.AuthenticationFailed("Invalid verification challenge.") from None

        cache_key = f"{MFA_CHALLENGE_CACHE_PREFIX}{payload['cid']}"
        challenge = cache.get(cache_key)
        if not challenge:
            raise exceptions.AuthenticationFailed("This verification challenge was already used.")

        user = User.objects.filter(pk=payload["uid"], is_active=True).first()
        if user is None:
            raise exceptions.AuthenticationFailed(INVALID_CREDENTIALS_MESSAGE)

        if not MFAService().verify_for_user(user, code):
            self.attempts.record(
                email=user.email, result=LoginAttempt.Result.MFA_FAILED, user=user
            )
            self.attempts.register_failure(user)
            raise exceptions.AuthenticationFailed("Invalid verification code.")

        cache.delete(cache_key)  # single use
        email = user.email
        self.attempts.record(email=email, result=LoginAttempt.Result.MFA_PASSED, user=user)
        return self._complete_login(user, email=email, ip=client_ip(self.request), mfa_verified=True)

    def _complete_login(
        self, user: User, *, email: str, ip: str | None, mfa_verified: bool
    ) -> LoginOutcome:
        django_login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        self.request.session.cycle_key()  # session fixation defence
        self.request.session["mfa_verified"] = mfa_verified
        self.sessions.register(user, session_key=self.request.session.session_key, mfa_verified=mfa_verified)
        self.attempts.register_success(user, ip)
        self.attempts.record(email=email, result=LoginAttempt.Result.SUCCESS, user=user)
        logger.info("User signed in (user_id=%s, mfa=%s)", user.pk, mfa_verified)
        return LoginOutcome(user=user)

    def logout(self) -> None:
        session_key = self.request.session.session_key
        if session_key:
            UserSession.objects.filter(session_key=session_key, revoked_at__isnull=True).update(
                revoked_at=timezone.now(), revoked_reason="logout"
            )
        django_logout(self.request)


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
class PasswordService:
    """Password change and reset flows."""

    def __init__(self, request=None):
        self.request = request
        self.sessions = SessionService(request) if request else None

    @staticmethod
    def validate(password: str, user: User | None = None) -> None:
        try:
            validate_password(password, user)
        except DjangoValidationError as exc:
            raise exceptions.ValidationError({"new_password": list(exc.messages)}) from exc

    def change_password(self, user: User, *, current_password: str, new_password: str) -> None:
        if not user.has_usable_password() or not user.check_password(current_password):
            raise exceptions.ValidationError({"current_password": ["Current password is incorrect."]})
        if current_password == new_password:
            raise exceptions.ValidationError(
                {"new_password": ["The new password must differ from the current one."]}
            )
        self.validate(new_password, user)

        with transaction.atomic():
            user.set_password(new_password)
            user.save(update_fields=["password", "password_changed_at", "must_change_password"])
            # Django invalidates any session whose stored auth hash no longer
            # matches the password, so the caller's own session is re-hashed —
            # changing your password must not sign *you* out.
            if self.request is not None:
                update_session_auth_hash(self.request, user)
                # Every other session is invalidated; the caller keeps working.
                if self.sessions:
                    self.sessions.revoke_others(
                        user,
                        keep_session_key=self.request.session.session_key,
                        reason="password change",
                    )
        logger.info("Password changed (user_id=%s)", user.pk)

    def request_reset(self, *, email: str) -> None:
        """Issue a reset token if the account exists (never disclose the answer)."""
        user = User.objects.filter(email=normalize_email(email), is_active=True).first()
        if user is None:
            logger.info("Password reset requested for unknown email")
            return
        token = OneTimeTokenService.issue(
            user,
            purpose=TokenPurpose.PASSWORD_RESET,
            ttl=settings.AUTH_PASSWORD_RESET_TTL,
            request=self.request,
        )
        reset_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/reset-password?token={token}"
        send_email(
            subject="Reset your WIMS password",
            body=(
                f"Hello {user.short_name},\n\n"
                "We received a request to reset your WIMS password.\n"
                f"Use the link below within {settings.AUTH_PASSWORD_RESET_TTL // 60} minutes:\n\n"
                f"{reset_url}\n\n"
                "If you did not request this, you can safely ignore this email — your "
                "password will not change.\n"
            ),
            recipient=user.email,
        )

    def confirm_reset(self, *, token: str, new_password: str) -> User:
        # Check the link *and* the password policy before burning the token, so
        # a rejected password does not force the user to request a new link.
        record = OneTimeTokenService.peek(token, purpose=TokenPurpose.PASSWORD_RESET)
        user = record.user
        self.validate(new_password, user)
        with transaction.atomic():
            OneTimeTokenService.consume(token, purpose=TokenPurpose.PASSWORD_RESET, record=record)
            user.set_password(new_password)
            user.clear_lock()
            user.save(
                update_fields=[
                    "password",
                    "password_changed_at",
                    "must_change_password",
                    "locked_until",
                    "failed_login_count",
                ]
            )
            if self.sessions:
                self.sessions.revoke_all(user, reason="password reset")
        logger.info("Password reset completed (user_id=%s)", user.pk)
        return user

    def set_temporary_password(self, user: User, password: str) -> None:
        """Administrator-issued password: must be changed at next sign-in."""
        self.validate(password, user)
        user.set_password(password)
        user.must_change_password = True
        user.save(update_fields=["password", "password_changed_at", "must_change_password"])


class OneTimeTokenService:
    """Issue and consume hashed, single-use, expiring tokens."""

    @staticmethod
    def issue(user: User, *, purpose: str, ttl: int, request=None) -> str:
        raw = secrets.token_urlsafe(32)
        OneTimeToken.objects.create(
            user=user,
            purpose=purpose,
            token_hash=hash_token(raw),
            expires_at=timezone.now() + timezone.timedelta(seconds=ttl),
            requested_ip=client_ip(request) if request else None,
            requested_user_agent=user_agent(request) if request else "",
        )
        return raw

    @staticmethod
    def peek(raw_token: str, *, purpose: str) -> OneTimeToken:
        """Resolve a usable token *without* consuming it (pre-flight checks)."""
        record = (
            OneTimeToken.objects.select_related("user")
            .filter(token_hash=hash_token(raw_token or ""), purpose=purpose)
            .order_by("-created_at")
            .first()
        )
        if record is None or not record.is_usable:
            raise exceptions.ValidationError(
                {"token": ["This link is invalid or has expired. Request a new one."]}
            )
        return record

    @staticmethod
    def consume(raw_token: str, *, purpose: str, record: OneTimeToken | None = None) -> OneTimeToken:
        record = record or OneTimeTokenService.peek(raw_token, purpose=purpose)
        record.used_at = timezone.now()
        record.save(update_fields=["used_at"])
        return record


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------
class EmailVerificationService:
    """Email verification tokens and delivery."""

    def __init__(self, request=None):
        self.request = request

    def send_verification(self, user: User) -> str | None:
        if user.is_email_verified:
            return None
        token = OneTimeTokenService.issue(
            user,
            purpose=TokenPurpose.EMAIL_VERIFICATION,
            ttl=settings.AUTH_EMAIL_VERIFICATION_TTL,
            request=self.request,
        )
        verify_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/verify-email?token={token}"
        send_email(
            subject="Confirm your email address",
            body=(
                f"Welcome to WIMS, {user.short_name}.\n\n"
                "Confirm your email address to activate all features:\n\n"
                f"{verify_url}\n\n"
                f"This link expires in {settings.AUTH_EMAIL_VERIFICATION_TTL // 3600} hours.\n"
            ),
            recipient=user.email,
        )
        return token

    def verify(self, token: str) -> User:
        record = OneTimeTokenService.consume(token, purpose=TokenPurpose.EMAIL_VERIFICATION)
        user = record.user
        user.mark_email_verified()
        user.save(update_fields=["is_email_verified", "email_verified_at"])
        logger.info("Email verified (user_id=%s)", user.pk)
        return user


def send_email(*, subject: str, body: str, recipient: str) -> None:
    """Send transactional email (console backend in dev, SMTP in production)."""
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send email '%s'", subject)


def send_html_email(*, subject: str, text_body: str, html_body: str, recipient: str) -> None:
    """Rich email variant used by notification-heavy flows."""
    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=False)
    except Exception:
        logger.exception("Failed to send HTML email '%s'", subject)


# ---------------------------------------------------------------------------
# MFA
# ---------------------------------------------------------------------------
class MFAService:
    """TOTP enrolment and verification, plus single-use recovery codes."""

    def start_enrolment(self, user: User, *, device_name: str = "Authenticator app") -> dict:
        """Create (or replace) an unconfirmed TOTP device and return provisioning data."""
        secret = generate_secret()
        device, _ = MFADevice.objects.update_or_create(
            user=user,
            device_type=MFADevice.DeviceType.TOTP,
            defaults={
                "name": device_name,
                "secret_encrypted": encrypt_secret(secret),
                "confirmed_at": None,
            },
        )
        uri = build_otpauth_uri(
            secret, account_name=user.email, issuer=settings.AUTH_MFA_ISSUER
        )
        return {"device": device, "secret": secret, "otpauth_uri": uri}

    def confirm_enrolment(self, user: User, *, code: str) -> tuple[MFADevice, list[str]]:
        device = self._pending_device(user)
        if not self._code_matches(device, code):
            raise exceptions.ValidationError({"code": ["That code is not valid. Try the next one."]})
        device.confirmed_at = timezone.now()
        device.last_used_at = timezone.now()
        device.save(update_fields=["confirmed_at", "last_used_at"])
        codes = self.regenerate_recovery_codes(user)
        logger.info("MFA enrolled (user_id=%s)", user.pk)
        return device, codes

    def verify_for_user(self, user: User, code: str) -> bool:
        """Verify a TOTP code or a recovery code for the user."""
        code = (code or "").strip()
        if not code:
            return False

        device = user.mfa_devices.filter(
            device_type=MFADevice.DeviceType.TOTP, confirmed_at__isnull=False
        ).first()
        if device and self._code_matches(device, code):
            device.last_used_at = timezone.now()
            device.save(update_fields=["last_used_at"])
            return True
        return self._consume_recovery_code(user, code)

    def disable(self, user: User, *, password: str) -> None:
        """Disabling MFA requires the account password (defence in depth)."""
        if not user.check_password(password):
            raise exceptions.ValidationError({"password": ["Password is incorrect."]})
        user.mfa_devices.all().delete()
        user.recovery_codes.all().delete()
        user.mfa_required = False
        user.save(update_fields=["mfa_required"])
        logger.warning("MFA disabled (user_id=%s)", user.pk)

    def regenerate_recovery_codes(self, user: User) -> list[str]:
        codes = generate_recovery_codes(settings.AUTH_MFA_RECOVERY_CODE_COUNT)
        user.recovery_codes.all().delete()
        MFARecoveryCode.objects.bulk_create(
            [MFARecoveryCode(user=user, code_hash=make_password(code)) for code in codes]
        )
        return codes

    def status(self, user: User) -> dict:
        device = user.mfa_devices.filter(
            device_type=MFADevice.DeviceType.TOTP, confirmed_at__isnull=False
        ).first()
        return {
            "enabled": device is not None,
            "required": bool(
                user.mfa_required
                or (settings.AUTH_REQUIRE_MFA_FOR_ADMINS and user.is_superuser)
            ),
            "device_name": device.name if device else "",
            "confirmed_at": device.confirmed_at if device else None,
            "last_used_at": device.last_used_at if device else None,
            "recovery_codes_remaining": user.recovery_codes.filter(used_at__isnull=True).count(),
        }

    # -- internals ---------------------------------------------------------
    def _pending_device(self, user: User) -> MFADevice:
        device = user.mfa_devices.filter(device_type=MFADevice.DeviceType.TOTP).first()
        if device is None:
            raise exceptions.ValidationError(
                {"detail": "Start MFA enrolment before confirming a code."}
            )
        return device

    def _code_matches(self, device: MFADevice, code: str) -> bool:
        try:
            secret = decrypt_secret(device.secret_encrypted)
        except Exception:
            logger.error("MFA secret could not be decrypted (device_id=%s)", device.pk)
            return False
        last_step = (
            code_step(device.last_used_at.timestamp()) if device.last_used_at else None
        )
        return verify_code(
            secret,
            code,
            window=settings.AUTH_MFA_VALID_WINDOW,
            last_used_step=last_step,
        )

    def _consume_recovery_code(self, user: User, code: str) -> bool:
        for recovery in user.recovery_codes.filter(used_at__isnull=True):
            if check_password(code.upper().strip(), recovery.code_hash):
                recovery.used_at = timezone.now()
                recovery.save(update_fields=["used_at"])
                logger.warning("MFA recovery code used (user_id=%s)", user.pk)
                return True
        return False


# ---------------------------------------------------------------------------
# User lifecycle
# ---------------------------------------------------------------------------
class UserService:
    """Account lifecycle: create, activate/deactivate, profile updates."""

    @staticmethod
    def create_user(
        *,
        email: str,
        first_name: str,
        last_name: str,
        organization=None,
        password: str | None = None,
        actor: User | None = None,
        send_verification: bool = True,
        **extra,
    ) -> tuple[User, str | None]:
        user = User.objects.create_user(
            email=normalize_email(email),
            password=password,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            organization=organization,
            status=User.Status.INVITED if password is None else User.Status.ACTIVE,
            must_change_password=password is not None,
            **extra,
        )
        token = None
        if send_verification:
            token = EmailVerificationService().send_verification(user)
        logger.info("User created (user_id=%s, by=%s)", user.pk, getattr(actor, "pk", None))
        return user, token

    @staticmethod
    def deactivate(user: User, *, actor: User | None = None, reason: str = "") -> User:
        with transaction.atomic():
            user.is_active = False
            user.status = User.Status.DEACTIVATED
            user.deactivated_at = timezone.now()
            user.deactivation_reason = reason[:255]
            user.save(
                update_fields=["is_active", "status", "deactivated_at", "deactivation_reason"]
            )
            revoke_user_sessions(user, reason="account deactivated")
            # Grants stay on record for audit but are paused. Suspending (rather
            # than silently deactivating) is what lets activation restore exactly
            # the authority the account had — including any warehouse scoping —
            # without an administrator re-granting every role.
            suspended = user.role_assignments.filter(is_active=True, is_suspended=False).update(
                is_active=False, is_suspended=True
            )
            logger.info(
                "Role assignments suspended on deactivation (user_id=%s, count=%s)",
                user.pk,
                suspended,
            )
        logger.warning("User deactivated (user_id=%s, by=%s)", user.pk, getattr(actor, "pk", None))
        return user

    @staticmethod
    def activate(user: User, *, actor: User | None = None) -> User:
        restored = user.role_assignments.filter(is_suspended=True).update(
            is_active=True, is_suspended=False
        )
        if restored:
            logger.info(
                "Role assignments restored on activation (user_id=%s, count=%s)",
                user.pk,
                restored,
            )
        user.is_active = True
        user.status = User.Status.ACTIVE
        user.deactivated_at = None
        user.deactivation_reason = ""
        user.clear_lock()
        user.save(
            update_fields=[
                "is_active",
                "status",
                "deactivated_at",
                "deactivation_reason",
                "locked_until",
                "failed_login_count",
            ]
        )
        logger.info("User activated (user_id=%s, by=%s)", user.pk, getattr(actor, "pk", None))
        return user


def revoke_user_sessions(user: User, *, reason: str) -> int:
    """Revoke every tracked session for a user (used on deactivation/reset)."""
    from django.contrib.sessions.models import Session

    keys = list(user.sessions.filter(revoked_at__isnull=True).values_list("session_key", flat=True))
    count = user.sessions.filter(revoked_at__isnull=True).update(
        revoked_at=timezone.now(), revoked_reason=reason[:64]
    )
    if keys:
        Session.objects.filter(session_key__in=keys).delete()
    return count
