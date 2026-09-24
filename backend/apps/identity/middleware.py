"""Identity middleware: enforce session revocation and idle expiry.

Django's session table has no notion of "this session was revoked"; we track
sessions ourselves (:class:`~apps.identity.models.UserSession`). This middleware
makes that tracking authoritative:

* a revoked session is flushed immediately and the caller gets ``401`` (API) or
  a redirect to the sign-in page (browser/admin);
* an expired session is treated the same way;
* ``last_seen_at``/``expires_at`` are refreshed (throttled) so sliding expiry
  works without a database write per request.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

logger = logging.getLogger("apps.identity.security")

_EXEMPT_PATH_PREFIXES = (
    "/api/v1/identity/auth/login",
    "/api/v1/identity/auth/mfa/verify",
    "/api/v1/identity/auth/password/reset",
    "/api/v1/identity/auth/email/verify",
)

# Paths that should never be intercepted (health probes, docs, static).
_IGNORED_PATH_PREFIXES = ("/api/v1/health", "/api/v1/schema", "/api/v1/docs", "/api/v1/redoc", "/static", "/media")


def _wants_json(request: HttpRequest) -> bool:
    return request.path.startswith("/api/")


class SessionRevocationMiddleware:
    """Reject requests whose tracked session has been revoked or expired."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path
        if path.startswith(_IGNORED_PATH_PREFIXES) or path.startswith(_EXEMPT_PATH_PREFIXES):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return self.get_response(request)

        session_key = request.session.session_key
        if not session_key:
            return self.get_response(request)

        from apps.identity.models import UserSession

        tracked = UserSession.objects.filter(session_key=session_key, user=user).first()

        if tracked is None:
            # Sessions created before tracking existed (e.g. Django admin CLI
            # login, freshly migrated databases) are adopted rather than killed.
            if getattr(request.session, "_wims_adopt_pending", False):
                return self.get_response(request)
            UserSession.objects.create(
                user=user,
                session_key=session_key,
                ip_address=request.META.get("REMOTE_ADDR") or None,
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255],
                expires_at=timezone.now()
                + timezone.timedelta(seconds=settings.SESSION_COOKIE_AGE),
            )
            return self.get_response(request)

        if tracked.revoked_at is not None or tracked.expires_at <= timezone.now():
            reason = "revoked" if tracked.revoked_at else "expired"
            logger.info(
                "Rejected %s session for user_id=%s (%s)", reason, user.pk, tracked.revoked_reason
            )
            request.session.flush()
            if _wants_json(request):
                return JsonResponse(
                    {
                        "error": {
                            "code": "session_invalid",
                            "message": "Your session is no longer valid. Please sign in again.",
                        }
                    },
                    status=401,
                )
            from django.shortcuts import redirect

            return redirect(f"/admin/login/?next={request.path}")

        # Sliding expiry refresh (throttled inside the service).
        from apps.identity.services import SessionService

        SessionService(request).touch(session_key)
        return self.get_response(request)
