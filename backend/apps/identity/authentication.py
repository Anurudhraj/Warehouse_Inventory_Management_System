"""Authentication classes.

Two credentials are accepted, in this order:

1. **Session cookie** (primary) — ``SessionAuthenticationWithChallenge``: DRF's
   session authentication plus an explicit ``WWW-Authenticate`` challenge so
   unauthenticated API calls receive **401** (not the generic DRF 403) — the
   frontend relies on that distinction to decide between "sign in again" and
   "you are not allowed to do this".
2. **Session token** (``Authorization: Bearer``) — opt-in fallback
   (``AUTH_ENABLE_TOKEN_FALLBACK``) for clients whose cookies the browser will
   not store or send, e.g. a cross-site embedded preview. It is the same opaque,
   server-tracked session credential (``UserSession.session_key``): revoking the
   session, deactivating the user or letting it expire kills both paths at once.

Neither path trusts the client for anything but *identification* — authorisation
is always resolved server-side by the authorization engine.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.authentication import (
    BaseAuthentication,
    SessionAuthentication,
    get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger("apps.identity.security")

TOKEN_TOUCH_INTERVAL_SECONDS = 60


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


class SessionTokenAuthentication(BaseAuthentication):
    """Opaque ``Authorization: Bearer <session_key>`` authentication.

    Disabled unless ``settings.AUTH_ENABLE_TOKEN_FALLBACK`` is on, in which case
    the sign-in response carries the token. Everything else is identical to the
    cookie path: the same revocation, idle-expiry and active-account checks
    apply, so a token can never outlive the session it belongs to.
    """

    keyword = b"bearer"

    def authenticate_header(self, request) -> str:
        return 'Bearer realm="wims"'

    def authenticate(self, request):
        if not getattr(settings, "AUTH_ENABLE_TOKEN_FALLBACK", False):
            return None

        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword:
            return None
        if len(parts) > 2:
            raise AuthenticationFailed("Invalid authorization header.")

        try:
            token = parts[1].decode("ascii")
        except (IndexError, UnicodeDecodeError):
            raise AuthenticationFailed("Invalid authorization header.") from None

        return self._authenticate_token(token)

    def _authenticate_token(self, token: str):
        from apps.identity.models import User, UserSession

        if not token:
            raise AuthenticationFailed("Invalid authorization header.")

        session = (
            UserSession.objects.select_related("user")
            .filter(session_key=token, revoked_at__isnull=True)
            .first()
        )
        if session is None:
            raise AuthenticationFailed("Session token is invalid or has been revoked.")

        if session.expires_at <= timezone.now():
            raise AuthenticationFailed("Session token has expired. Please sign in again.")

        user: User = session.user
        if not user.is_active:
            session.revoke(reason="account inactive")
            raise AuthenticationFailed("This account is not active.")

        self._touch(session)
        # Exposed as ``request.auth`` so views (logout, session listing) can act
        # on the very session that authenticated the call.
        return (user, session)

    @staticmethod
    def _touch(session) -> None:
        """Sliding expiry, throttled so a busy client does not write per request."""
        from apps.identity.models import UserSession

        cache_key = f"session-touch:{session.session_key}"
        if cache.get(cache_key):
            return
        cache.set(cache_key, 1, TOKEN_TOUCH_INTERVAL_SECONDS)
        UserSession.objects.filter(pk=session.pk, revoked_at__isnull=True).update(
            last_seen_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(seconds=settings.SESSION_COOKIE_AGE),
        )
