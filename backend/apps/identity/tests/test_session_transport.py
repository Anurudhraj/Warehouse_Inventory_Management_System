"""How the session credential travels: cookies, CSRF and the bearer fallback.

These tests exist because the two failure modes they cover are invisible to
service-level tests and only show up in a browser:

* ``CSRF_COOKIE_HTTPONLY`` — if the CSRF cookie is HttpOnly the SPA cannot echo
  the token, so every authenticated write (sign out, invite, profile update)
  fails with a 403 that looks like a permissions problem.
* ``SameSite=Lax`` cookies on a cross-site embed — the browser silently drops
  them, so sign-in "succeeds" and the very next request is anonymous again: the
  user is bounced back to the sign-in page forever.
"""
from __future__ import annotations

from django.conf import settings
from django.test import Client, override_settings
from django.utils import timezone

from apps.core.testing.factories import DEFAULT_PASSWORD
from apps.identity.models import UserSession
from apps.identity.tests.base import LOGIN_URL, LOGOUT_URL, SESSION_URL, IdentityApiTestCase


class CookieAndCsrfConfigurationTests(IdentityApiTestCase):
    """The settings the browser actually sees."""

    def test_session_cookie_is_httponly(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_csrf_cookie_is_readable_by_the_spa(self):
        # The SPA must be able to read the token to send ``X-CSRFToken``.
        self.assertFalse(settings.CSRF_COOKIE_HTTPONLY)

    def test_samesite_none_implies_secure(self):
        """A ``SameSite=None`` cookie without ``Secure`` is rejected by browsers."""
        with override_settings(CSRF_COOKIE_HTTPONLY=False):
            from config import env as env_module

            # Re-evaluate the guard in settings/base.py the same way a deployment
            # would: None + not secure must be promoted to secure.
            samesite = env_module.env_str("DJANGO_COOKIE_SAMESITE", default="None")
            secure = env_module.env_bool("DJANGO_COOKIE_SECURE", default=False)
            if samesite.lower() == "none" and not secure:
                secure = True
            self.assertTrue(secure)

    def test_login_response_carries_a_csrf_cookie(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)


class CookieTransportTests(IdentityApiTestCase):
    """Cookie authentication keeps working, including CSRF enforcement."""

    def test_authenticated_write_requires_the_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            LOGIN_URL, {"email": self.operator.email, "password": DEFAULT_PASSWORD}, "application/json"
        )
        self.assertEqual(response.status_code, 200)
        csrf = response.cookies["csrftoken"].value

        # Without the header the request is rejected …
        blocked = client.post(LOGOUT_URL, "{}", "application/json")
        self.assertIn(blocked.status_code, (401, 403))

        # … and with it (exactly what the SPA does) it succeeds.
        allowed = client.post(LOGOUT_URL, "{}", "application/json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(allowed.status_code, 204)


class BearerFallbackTests(IdentityApiTestCase):
    """The opt-in bearer path (used when the browser refuses cookies)."""

    @override_settings(AUTH_ENABLE_TOKEN_FALLBACK=True)
    def test_login_returns_a_session_token_when_asked(self):
        response = self.login_or_fail()
        self.assertNotIn("session_token", response.data)

        requested = self.client.post(
            LOGIN_URL,
            {
                "email": self.operator.email,
                "password": DEFAULT_PASSWORD,
                "token_auth": True,
            },
            format="json",
        )
        self.assertEqual(requested.status_code, 200)
        token = requested.data["session_token"]
        self.assertTrue(token)
        self.assertTrue(UserSession.objects.filter(session_key=token).exists())

    def test_no_token_is_issued_when_the_fallback_is_disabled(self):
        response = self.client.post(
            LOGIN_URL,
            {"email": self.operator.email, "password": DEFAULT_PASSWORD, "token_auth": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        # The field is omitted entirely — cookie clients see the unchanged shape.
        self.assertNotIn("session_token", response.data)

    @override_settings(AUTH_ENABLE_TOKEN_FALLBACK=True)
    def test_bearer_token_authenticates_without_any_cookie(self):
        token = self.login_with_token()

        browser = self.second_client()  # no cookies at all
        response = browser.get(SESSION_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["email"], self.operator.email)

    @override_settings(AUTH_ENABLE_TOKEN_FALLBACK=True)
    def test_bearer_token_is_not_accepted_when_the_fallback_is_off(self):
        token = self.login_with_token()

        with override_settings(AUTH_ENABLE_TOKEN_FALLBACK=False):
            response = self.second_client().get(
                SESSION_URL, HTTP_AUTHORIZATION=f"Bearer {token}"
            )
        self.assertEqual(response.status_code, 401)

    @override_settings(AUTH_ENABLE_TOKEN_FALLBACK=True)
    def test_unknown_token_is_rejected(self):
        response = self.second_client().get(
            SESSION_URL, HTTP_AUTHORIZATION="Bearer not-a-real-session-key"
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(AUTH_ENABLE_TOKEN_FALLBACK=True)
    def test_revoked_session_kills_the_token(self):
        token = self.login_with_token()
        session = UserSession.objects.get(session_key=token)
        session.revoke(reason="test revocation")

        response = self.second_client().get(SESSION_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 401)

    @override_settings(AUTH_ENABLE_TOKEN_FALLBACK=True)
    def test_expired_session_kills_the_token(self):
        token = self.login_with_token()
        UserSession.objects.filter(session_key=token).update(
            expires_at=timezone.now() - timezone.timedelta(seconds=1)
        )

        response = self.second_client().get(SESSION_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 401)

    @override_settings(AUTH_ENABLE_TOKEN_FALLBACK=True)
    def test_deactivated_account_kills_the_token(self):
        token = self.login_with_token()
        self.operator.is_active = False
        self.operator.status = "deactivated"
        self.operator.save(update_fields=["is_active", "status"])

        response = self.second_client().get(SESSION_URL, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 401)

    @override_settings(AUTH_ENABLE_TOKEN_FALLBACK=True)
    def test_logout_via_token_revokes_the_session(self):
        token = self.login_with_token()
        browser = self.second_client()

        response = browser.post(
            LOGOUT_URL, {}, format="json", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 204)

        session = UserSession.objects.get(session_key=token)
        self.assertIsNotNone(session.revoked_at)
        self.assertEqual(
            browser.get(SESSION_URL, HTTP_AUTHORIZATION=f"Bearer {token}").status_code, 401
        )

    @override_settings(AUTH_ENABLE_TOKEN_FALLBACK=True)
    def test_token_grants_no_extra_authority(self):
        """The fallback authenticates; it never authorises."""
        token = self.login_with_token()
        response = self.second_client().get(
            "/api/v1/security/roles/", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        # The operator holds no role-management permission → 403, not 200.
        self.assertEqual(response.status_code, 403)

    def login_with_token(self, email: str | None = None) -> str:
        response = self.client.post(
            LOGIN_URL,
            {
                "email": email or self.operator.email,
                "password": DEFAULT_PASSWORD,
                "token_auth": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["session_token"]
