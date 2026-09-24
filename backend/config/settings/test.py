"""Test settings — fast, deterministic, no external side effects."""

from .base import *

ENVIRONMENT = "test"

DEBUG = False

if not SECRET_KEY:
    SECRET_KEY = "test-secret-key-not-used-in-any-real-environment"

# Faster password hashing in tests (never used outside the test suite).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Hermetic infrastructure: no Redis, no SMTP — tests must be runnable anywhere.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "wims-tests",
    }
}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Authentication throttling is exercised explicitly (the suites that assert it
# lower the rate with ``override_settings``), so the defaults must not trip on
# ordinary fixtures.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        "login": "1000/min",
        "password_reset": "1000/min",
        "email": "1000/min",
        "mfa": "1000/min",
    },
}

LOGGING["root"]["level"] = "WARNING"
for _logger in LOGGING["loggers"].values():
    _logger["level"] = "WARNING"
