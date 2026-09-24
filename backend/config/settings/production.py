"""Production settings — secure defaults, fail fast on misconfiguration."""

from django.core.exceptions import ImproperlyConfigured

from .base import *
from .base import env

ENVIRONMENT = "production"

# ---------------------------------------------------------------------------
# Hard requirements — fail fast instead of starting insecure
# ---------------------------------------------------------------------------
DEBUG = False
if env.env_bool("DJANGO_DEBUG", default=False):
    raise ImproperlyConfigured("DJANGO_DEBUG must be false in production.")

SECRET_KEY = env.env_str("DJANGO_SECRET_KEY", required=True)

ALLOWED_HOSTS = env.env_list("DJANGO_ALLOWED_HOSTS", required=True)
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must not be empty in production.")

DATABASES["default"]["PASSWORD"] = env.env_str("POSTGRES_PASSWORD", required=True)

# ---------------------------------------------------------------------------
# TLS / secure transport (terminate TLS at the proxy; Django trusts the
# X-Forwarded-Proto header set by nginx).
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.env_bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_NAME = "__Host-sessionid"
CSRF_COOKIE_NAME = "__Host-csrftoken"

SECURE_HSTS_SECONDS = env.env_int("SECURE_HSTS_SECONDS", default=365 * 24 * 3600)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = env.env_bool("SECURE_HSTS_PRELOAD", default=False)

# ---------------------------------------------------------------------------
# Cross-origin requests must be explicitly allowed — never wildcards.
# ---------------------------------------------------------------------------
if not CORS_ALLOWED_ORIGINS and not CORS_ALLOWED_ORIGIN_REGEXES:
    raise ImproperlyConfigured(
        "CORS_ALLOWED_ORIGINS must list the frontend origin(s) in production."
    )

CSRF_TRUSTED_ORIGINS = env.env_list("DJANGO_CSRF_TRUSTED_ORIGINS", required=True)

# ---------------------------------------------------------------------------
# API documentation is disabled in production by default (set
# ENABLE_API_DOCS=true to expose them behind authentication).
# ---------------------------------------------------------------------------
ENABLE_API_DOCS = env.env_bool("ENABLE_API_DOCS", default=False)
