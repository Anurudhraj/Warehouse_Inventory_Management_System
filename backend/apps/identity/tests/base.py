"""Shared fixtures for the identity API suites.

Every suite drives the HTTP API (never the services directly) so the tests
cover the same code path a browser/app uses, including permission checks,
serialization and the session middleware.
"""
from __future__ import annotations

import re
import time
from contextlib import contextmanager
from unittest import mock

from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

from apps.core.testing.factories import (
    DEFAULT_PASSWORD,
    assign,
    make_branch,
    make_org_admin,
    make_organization,
    make_user,
    make_warehouse,
)
from apps.identity.models import LoginAttempt, OneTimeToken, UserSession
from apps.security.totp import generate_code

TOKEN_PATTERN = re.compile(r"token=([A-Za-z0-9_\-\.]+)")


@contextmanager
def throttle_rate(scope: str, rate: str):
    """Temporarily change a DRF throttle rate.

    DRF binds ``SimpleRateThrottle.THROTTLE_RATES`` at import time, so
    ``override_settings(REST_FRAMEWORK=...)`` alone cannot change it — the
    class-level mapping has to be patched.
    """
    from rest_framework.throttling import ScopedRateThrottle

    with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {scope: rate}):
        yield


def totp_code(secret: str) -> str:
    """A TOTP code for the **next** step.

    Accepted codes are replay-protected (a step that was already used is
    rejected), and enrolment consumes the current step, so tests authenticate
    with the following step — still inside the ±1-step acceptance window.
    """
    return generate_code(secret, at_time=time.time() + 30)

LOGIN_URL = "/api/v1/identity/auth/login/"
LOGOUT_URL = "/api/v1/identity/auth/logout/"
SESSION_URL = "/api/v1/identity/auth/session/"


class IdentityApiTestCase(APITestCase):
    """One tenant, one warehouse, one operator, one organization admin."""

    @classmethod
    def setUpTestData(cls):
        cls.acme = make_organization("ACME", "Acme Distribution")
        cls.branch = make_branch(cls.acme, "ACME-B1", name="Acme North")
        cls.warehouse = make_warehouse(cls.branch, "WH-A1", name="Acme WH 1")

        cls.operator = make_user("operator@acme.test", organization=cls.acme)
        assign(cls.operator, "warehouse_operator", warehouse=cls.warehouse)

        cls.org_admin = make_org_admin(cls.acme, "admin@acme.test")

    def setUp(self):
        # Throttle and MFA-challenge counters live in the cache: clear them so
        # every test starts from a known state.
        cache.clear()
        mail.outbox.clear()

    # --- helpers ----------------------------------------------------------
    def login(self, email: str | None = None, password: str = DEFAULT_PASSWORD, client=None):
        client = client or self.client
        response = client.post(
            LOGIN_URL,
            {"email": email or self.operator.email, "password": password},
            format="json",
        )
        return response

    def login_or_fail(
        self, email: str | None = None, password: str = DEFAULT_PASSWORD, client=None
    ):
        response = self.login(email, password, client)
        assert response.status_code == 200, response.data
        return response

    def logout(self, client=None):
        return (client or self.client).post(LOGOUT_URL, format="json")

    def second_client(self) -> APIClient:
        """A separate browser/session for the same or another user."""
        return APIClient()

    def session_of(self, user, *, active: bool = True) -> UserSession:
        qs = UserSession.objects.filter(user=user)
        return qs.filter(revoked_at__isnull=True).first() if active else qs.first()

    def latest_attempt(self, user=None) -> LoginAttempt:
        qs = LoginAttempt.objects.all()
        if user is not None:
            qs = qs.filter(user=user)
        return qs.order_by("-created_at", "-id").first()

    @staticmethod
    def token_from_email(message) -> str:
        match = TOKEN_PATTERN.search(message.body)
        assert match, f"no token in email body:\n{message.body}"
        return match.group(1)

    @staticmethod
    def tokens_for(user, purpose: str) -> int:
        return OneTimeToken.objects.filter(user=user, purpose=purpose).count()
