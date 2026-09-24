"""Authentication classes.

Session authentication for the browser SPA, with an explicit
``WWW-Authenticate`` challenge so unauthenticated API calls receive **401**
(not the generic DRF 403) — the frontend relies on that distinction to decide
between "sign in again" and "you are not allowed to do this".
"""
from __future__ import annotations

from rest_framework.authentication import SessionAuthentication


class SessionAuthenticationWithChallenge(SessionAuthentication):
    """Session auth + RFC 7235 challenge header (→ 401 for anonymous callers)."""

    def authenticate_header(self, request) -> str:
        return 'Session realm="wims"'


class ChallengeHeaderMixin:
    """Keeps ``401`` for unauthenticated failures on views that use no authenticator.

    DRF rewrites a 401 into 403 when the view cannot offer a challenge
    (``APIView.handle_exception``). Anonymous endpoints that can fail
    authentication — sign-in, MFA verification, password reset, email
    verification — still answer 401, so the SPA can tell the two apart.
    """

    def get_authenticate_header(self, request) -> str:
        return 'Session realm="wims"'
