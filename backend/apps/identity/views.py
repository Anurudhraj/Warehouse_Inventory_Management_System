"""Identity API views.

Authentication endpoints (login, MFA, password reset/change, email
verification), the self-service profile/session surface and the administrative
user-management endpoints.

Every administrative endpoint enforces authorization **on the backend** through
the security module's permission classes and the service layer — the frontend
merely hides buttons.
"""
from __future__ import annotations

import logging

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination
from apps.identity.authentication import ChallengeHeaderMixin
from apps.identity.models import LoginAttempt, User, UserSession
from apps.identity.serializers import (
    DeactivateUserSerializer,
    EmailVerificationSerializer,
    LoginAttemptSerializer,
    LoginSerializer,
    MFAChallengeSerializer,
    MFAConfirmSerializer,
    MFADeviceSerializer,
    MFADisableSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    SetPasswordSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserSessionSerializer,
    UserSummarySerializer,
    UserUpdateSerializer,
)
from apps.identity.services import (
    AuthenticationService,
    EmailVerificationService,
    MFAService,
    PasswordService,
    SessionService,
    UserService,
)
from apps.security.authorization import AuthorizationService, authorization_for
from apps.security.permissions import (
    HasScopedPermission,
    IsAuthenticatedAndActive,
    require_permission,
)

logger = logging.getLogger("apps.identity.api")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
class LoginView(ChallengeHeaderMixin, APIView):
    """Password sign-in. Returns either a session or an MFA challenge."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = AuthenticationService(request).login(**serializer.validated_data)

        if outcome.mfa_required:
            return Response(
                {
                    "mfa_required": True,
                    "challenge_token": outcome.challenge_token,
                    "user": {"email": outcome.user.email, "first_name": outcome.user.first_name},
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "mfa_required": False,
                "user": ProfileSerializer(outcome.user, context={"request": request}).data,
                "permissions": sorted(
                    AuthorizationService(outcome.user).effective_permission_codes()
                ),
            },
            status=status.HTTP_200_OK,
        )


class MFALoginVerifyView(ChallengeHeaderMixin, APIView):
    """Second step of a password+MFA sign-in."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_scope = "mfa"

    def post(self, request):
        serializer = MFAChallengeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = AuthenticationService(request).verify_mfa_challenge(
            challenge_token=serializer.validated_data["challenge_token"],
            code=serializer.validated_data["code"],
        )
        return Response(
            {
                "mfa_required": False,
                "user": ProfileSerializer(outcome.user, context={"request": request}).data,
                "permissions": sorted(
                    AuthorizationService(outcome.user).effective_permission_codes()
                ),
            }
        )


class LogoutView(ChallengeHeaderMixin, APIView):
    """End the current session (tracked session revoked server-side)."""

    permission_classes = [AllowAny]

    def post(self, request):
        if request.user and request.user.is_authenticated:
            AuthenticationService(request).logout()
        else:
            request.session.flush()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionDetailView(APIView):
    """Current session + identity + effective permissions (frontend bootstrap)."""

    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        user = request.user
        service = authorization_for(request)
        return Response(
            {
                "authenticated": True,
                "user": ProfileSerializer(user, context={"request": request}).data,
                "permissions": sorted(service.effective_permission_codes()),
                "organizations": sorted(service.accessible_organization_ids()),
                "warehouses": sorted(service.accessible_warehouse_ids()),
                "is_platform_admin": service.is_platform_admin,
            }
        )


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticatedAndActive]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PasswordService(request).change_password(
            request.user,
            current_password=serializer.validated_data["current_password"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response({"detail": "Password updated. Other sessions were signed out."})


class PasswordResetRequestView(APIView):
    """Request a reset link. Always answers 202 to avoid account enumeration."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PasswordService(request).request_reset(email=serializer.validated_data["email"])
        return Response(
            {
                "detail": (
                    "If an account exists for that email address, a password reset link "
                    "has been sent."
                )
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetConfirmView(ChallengeHeaderMixin, APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PasswordService(request).confirm_reset(
            token=serializer.validated_data["token"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response({"detail": "Password reset. You can now sign in."})


class EmailVerificationView(ChallengeHeaderMixin, APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_scope = "email"

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = EmailVerificationService(request).verify(serializer.validated_data["token"])
        return Response({"detail": "Email address verified.", "email": user.email})


class EmailVerificationResendView(APIView):
    permission_classes = [IsAuthenticatedAndActive]
    throttle_scope = "email"

    def post(self, request):
        if request.user.is_email_verified:
            return Response({"detail": "This email address is already verified."})
        EmailVerificationService(request).send_verification(request.user)
        return Response({"detail": "Verification email sent."}, status=status.HTTP_202_ACCEPTED)


# ---------------------------------------------------------------------------
# Profile / self-service
# ---------------------------------------------------------------------------
class ProfileView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        return Response(ProfileSerializer(request.user, context={"request": request}).data)

    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class SessionViewSet(viewsets.ReadOnlyModelViewSet):
    """Tracked sessions for the current user (list + remote revocation)."""

    serializer_class = UserSessionSerializer
    permission_classes = [IsAuthenticatedAndActive]
    pagination_class = StandardPagination

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user).order_by("-last_seen_at")

    @action(detail=False, methods=["get"])
    def current(self, request):
        session = SessionService(request).current_session(request.user)
        if session is None:
            raise NotFound("No tracked session for this request.")
        return Response(self.get_serializer(session).data)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        session = self.get_object()
        if session.user_id != request.user.id:
            raise NotFound("Not found.")
        if session.session_key == request.session.session_key:
            raise ValidationError({"detail": "Use sign-out to end the current session."})
        SessionService(request).revoke(session, reason="revoked by user")
        return Response({"detail": "Session revoked."})

    @action(detail=False, methods=["post"], url_path="revoke-all")
    def revoke_all(self, request):
        current_key = request.session.session_key
        count = SessionService(request).revoke_others(
            request.user, keep_session_key=current_key, reason="revoked by user"
        )
        return Response({"detail": f"{count} other session(s) revoked.", "revoked": count})


# ---------------------------------------------------------------------------
# MFA
# ---------------------------------------------------------------------------
class MFAStatusView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        service = MFAService()
        return Response(
            {
                **service.status(request.user),
                "devices": MFADeviceSerializer(request.user.mfa_devices.all(), many=True).data,
            }
        )


class MFAEnrolView(APIView):
    """Start TOTP enrolment: returns the shared secret and otpauth URI once."""

    permission_classes = [IsAuthenticatedAndActive]
    throttle_scope = "mfa"

    def post(self, request):
        data = MFAService().start_enrolment(
            request.user, device_name=request.data.get("name") or "Authenticator app"
        )
        return Response(
            {
                "secret": data["secret"],
                "otpauth_uri": data["otpauth_uri"],
                "device": MFADeviceSerializer(data["device"]).data,
                "detail": "Scan the URI, then confirm with a generated code.",
            },
            status=status.HTTP_201_CREATED,
        )


class MFAConfirmView(APIView):
    """Confirm enrolment; returns single-use recovery codes exactly once."""

    permission_classes = [IsAuthenticatedAndActive]
    throttle_scope = "mfa"

    def post(self, request):
        serializer = MFAConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device, codes = MFAService().confirm_enrolment(
            request.user, code=serializer.validated_data["code"]
        )
        return Response(
            {
                "device": MFADeviceSerializer(device).data,
                "recovery_codes": codes,
                "detail": "Multi-factor authentication enabled. Store the recovery codes safely.",
            }
        )


class MFADisableView(APIView):
    permission_classes = [IsAuthenticatedAndActive]
    throttle_scope = "mfa"

    def post(self, request):
        serializer = MFADisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        MFAService().disable(request.user, password=serializer.validated_data["password"])
        return Response({"detail": "Multi-factor authentication disabled."})


class MFARecoveryCodesView(APIView):
    permission_classes = [IsAuthenticatedAndActive]
    throttle_scope = "mfa"

    def post(self, request):
        if not request.user.has_mfa_enabled:
            raise ValidationError({"detail": "Enable MFA before generating recovery codes."})
        codes = MFAService().regenerate_recovery_codes(request.user)
        return Response({"recovery_codes": codes})


# ---------------------------------------------------------------------------
# Administrative user management
# ---------------------------------------------------------------------------
class UserViewSet(viewsets.ModelViewSet):
    """User administration, scoped to the caller's accessible organizations.

    * list/retrieve require ``user.view`` in scope
    * create/update/deactivate require ``user.manage``
    * a user can always read and edit *their own* record
    """

    permission_classes = [IsAuthenticatedAndActive, HasScopedPermission]
    pagination_class = StandardPagination
    search_fields = ["email", "first_name", "last_name", "job_title", "reference"]
    ordering_fields = ["last_name", "email", "created_at", "last_login_at"]
    ordering = ["last_name", "first_name"]

    def get_queryset(self):
        service = authorization_for(self.request)
        qs = User.objects.select_related("organization").order_by("last_name", "first_name")

        if service.is_platform_admin:
            pass
        else:
            org_ids = service.accessible_organization_ids()
            qs = qs.filter(Q(organization_id__in=org_ids) | Q(id=self.request.user.id))

        filters_map = {
            "status": self.request.query_params.get("status"),
            "organization": self.request.query_params.get("organization"),
            "is_active": self.request.query_params.get("is_active"),
            "role": self.request.query_params.get("role"),
        }
        if filters_map["status"]:
            qs = qs.filter(status=filters_map["status"])
        if filters_map["organization"]:
            qs = qs.filter(organization_id=filters_map["organization"])
        if filters_map["is_active"] is not None:
            qs = qs.filter(is_active=filters_map["is_active"].lower() in ("1", "true", "yes"))
        if filters_map["role"]:
            qs = qs.filter(role_assignments__role__code=filters_map["role"]).distinct()

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(reference__icontains=search)
            )
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return UserSummarySerializer
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        return UserSerializer

    def get_required_permissions(self) -> tuple[str, ...]:
        if self.action in ("list", "retrieve"):
            return ("user.view",)
        return ("user.manage",)

    @property
    def required_permissions(self) -> tuple[str, ...]:  # DRF reads this first
        return self.get_required_permissions()

    def _assert_can_manage(self, target: User) -> None:
        allowed, reason = authorization_for(self.request).can_manage_user(target)
        if not allowed:
            if not authorization_for(self.request).can_access_organization(
                target.organization
            ) and target.organization_id:
                raise NotFound("Not found.")
            raise PermissionDenied(reason)

    def create(self, request, *args, **kwargs):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        service = authorization_for(request)

        organization = request.user.organization
        if data.get("organization_id"):
            from apps.organizations.models import Organization

            organization = Organization.objects.filter(pk=data["organization_id"]).first()
            if organization is None:
                raise ValidationError({"organization_id": ["Unknown organization."]})
        # Creating a user in a foreign organization is not permitted.
        if organization is not None:
            service.ensure_organization_access(organization)
        elif not service.is_platform_admin:
            raise PermissionDenied(
                "Specify an organization you have access to when creating a user."
            )

        if data.get("password") is None and not data.get("send_verification_email", True):
            raise ValidationError(
                {"send_verification_email": ["An invited user must receive a verification email."]}
            )

        user, _token = UserService.create_user(
            email=data["email"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone=data.get("phone", ""),
            job_title=data.get("job_title", ""),
            organization=organization,
            password=data.get("password"),
            actor=request.user,
            send_verification=data.get("send_verification_email", True),
            mfa_required=data.get("mfa_required", False),
        )
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        self._assert_can_manage(instance)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        self._assert_can_manage(instance)
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Users are never hard-deleted: deactivate to preserve the audit trail."""
        raise ValidationError(
            {"detail": "Users are deactivated, never deleted. Use POST activate/deactivate."}
        )

    @action(detail=True, methods=["post"])
    @require_permission("user.manage")
    def activate(self, request, pk=None):
        user = self.get_object()
        self._assert_can_manage(user)
        UserService.activate(user, actor=request.user)
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    @require_permission("user.manage")
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user.id == request.user.id:
            raise ValidationError({"detail": "You cannot deactivate your own account."})
        self._assert_can_manage(user)
        serializer = DeactivateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        UserService.deactivate(
            user, actor=request.user, reason=serializer.validated_data.get("reason", "")
        )
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="set-password")
    @require_permission("user.manage")
    def set_password(self, request, pk=None):
        user = self.get_object()
        self._assert_can_manage(user)
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PasswordService().set_temporary_password(user, serializer.validated_data["password"])
        if serializer.validated_data.get("must_change_password", True):
            user.must_change_password = True
            user.save(update_fields=["must_change_password"])
        return Response({"detail": "Temporary password set; the user must change it at next sign-in."})

    @action(detail=True, methods=["post"], url_path="resend-verification")
    @require_permission("user.manage")
    def resend_verification(self, request, pk=None):
        user = self.get_object()
        self._assert_can_manage(user)
        token = EmailVerificationService(request).send_verification(user)
        return Response({"detail": "Verification email sent." if token else "Already verified."})

    @action(detail=True, methods=["post"], url_path="revoke-sessions")
    @require_permission("user.manage")
    def revoke_sessions(self, request, pk=None):
        user = self.get_object()
        self._assert_can_manage(user)
        from apps.identity.services import revoke_user_sessions

        count = revoke_user_sessions(user, reason="revoked by administrator")
        return Response({"detail": f"{count} session(s) revoked.", "revoked": count})

    @action(detail=True, methods=["get"], url_path="sessions")
    @require_permission("session.view")
    def sessions(self, request, pk=None):
        user = self.get_object()
        self._assert_can_manage(user)
        page = self.paginate_queryset(user.sessions.all()[:100])
        serializer = UserSessionSerializer(page or user.sessions.all(), many=True, context={"request": request})
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)


class LoginAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """Login-attempt ledger.

    Users always see their own attempts; ``audit.view`` in scope is required to
    see attempts for other accounts.
    """

    serializer_class = LoginAttemptSerializer
    permission_classes = [IsAuthenticatedAndActive]
    pagination_class = StandardPagination
    ordering = ["-created_at"]

    def get_queryset(self):
        service = authorization_for(self.request)
        qs = LoginAttempt.objects.select_related("user").order_by("-created_at")

        if service.is_platform_admin:
            return qs

        own = Q(user=self.request.user) | Q(email_attempted=self.request.user.email)
        if self._has_audit_scope():
            # Auditors see their own attempts plus every account in the tenants
            # they can reach — never another organization's ledger.
            return qs.filter(
                own | Q(user__organization_id__in=service.accessible_organization_ids())
            )
        return qs.filter(own)

    def _has_audit_scope(self) -> bool:
        service = authorization_for(self.request)
        return any(
            service.has_permission("audit.view", organization=organization)
            for organization in self._accessible_orgs()
        )

    def _accessible_orgs(self):
        from apps.organizations.models import Organization

        service = authorization_for(self.request)
        return Organization.objects.filter(id__in=service.accessible_organization_ids())


class TokenInspectionView(ChallengeHeaderMixin, APIView):
    """Check whether a one-time token (password reset / email verification) is
    still usable — lets the frontend show a friendly "link expired" state
    before asking the user to type a new password.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_scope = "email"

    def post(self, request):
        from apps.identity.models import OneTimeToken, TokenPurpose
        from apps.security.crypto import hash_token

        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purpose = request.data.get("purpose") or TokenPurpose.PASSWORD_RESET
        if purpose not in TokenPurpose.values:
            raise ValidationError({"purpose": ["Unknown token purpose."]})

        record = (
            OneTimeToken.objects.filter(
                token_hash=hash_token(serializer.validated_data["token"]), purpose=purpose
            )
            .order_by("-created_at")
            .first()
        )
        if record is None or not record.is_usable:
            raise ValidationError({"token": ["This link is invalid or has expired."]})
        return Response({"valid": True, "purpose": purpose})
