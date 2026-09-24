"""Identity API routes — mounted at ``/api/v1/identity/``.

Authentication
    POST   auth/login/                     password sign-in
    POST   auth/mfa/verify/                second step of an MFA sign-in
    POST   auth/logout/                    end the current session
    GET    auth/session/                   current identity + permissions
    POST   auth/password/change/           change own password
    POST   auth/password/reset/            request a reset link
    POST   auth/password/reset/confirm/    consume the reset link
    POST   auth/password/reset/validate/   check a link before showing the form
    POST   auth/email/verify/              confirm an email address
    POST   auth/email/resend/              resend the verification email

Self-service
    GET/PATCH profile/
    GET/POST  sessions/, POST sessions/<id>/revoke/, POST sessions/revoke-all/
    GET/POST  mfa/, POST mfa/enrol/, mfa/confirm/, mfa/disable/, mfa/recovery-codes/

Administration
    /users/                    CRUD + activate/deactivate/set-password/…
    /users/<id>/sessions/      sessions of a user
    /login-attempts/           authentication audit ledger
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.identity.views import (
    EmailVerificationResendView,
    EmailVerificationView,
    LoginAttemptViewSet,
    LoginView,
    LogoutView,
    MFAConfirmView,
    MFADisableView,
    MFAEnrolView,
    MFALoginVerifyView,
    MFARecoveryCodesView,
    MFAStatusView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProfileView,
    SessionDetailView,
    SessionViewSet,
    TokenInspectionView,
    UserViewSet,
)

app_name = "identity"

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("sessions", SessionViewSet, basename="session")
router.register("login-attempts", LoginAttemptViewSet, basename="login-attempt")

auth_patterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("mfa/verify/", MFALoginVerifyView.as_view(), name="auth-mfa-verify"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("session/", SessionDetailView.as_view(), name="auth-session"),
    path("password/change/", PasswordChangeView.as_view(), name="auth-password-change"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path(
        "password/reset/validate/",
        TokenInspectionView.as_view(),
        name="auth-password-reset-validate",
    ),
    path("email/verify/", EmailVerificationView.as_view(), name="auth-email-verify"),
    path("email/resend/", EmailVerificationResendView.as_view(), name="auth-email-resend"),
]

profile_patterns = [
    path("profile/", ProfileView.as_view(), name="profile"),
    path("mfa/", MFAStatusView.as_view(), name="mfa-status"),
    path("mfa/enrol/", MFAEnrolView.as_view(), name="mfa-enrol"),
    path("mfa/confirm/", MFAConfirmView.as_view(), name="mfa-confirm"),
    path("mfa/disable/", MFADisableView.as_view(), name="mfa-disable"),
    path("mfa/recovery-codes/", MFARecoveryCodesView.as_view(), name="mfa-recovery-codes"),
]

urlpatterns = [
    path("auth/", include(auth_patterns)),
    path("", include(profile_patterns)),
    path("", include(router.urls)),
]
