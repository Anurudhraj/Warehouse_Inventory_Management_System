"""Test settings — fast, deterministic, no external side effects."""

from .base import *

ENVIRONMENT = "test"

DEBUG = False

if not SECRET_KEY:
    SECRET_KEY = "test-secret-key-not-used-in-any-real-environment"

# Faster password hashing in tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHash"]

LOGGING["root"]["level"] = "WARNING"
for _logger in LOGGING["loggers"].values():
    _logger["level"] = "WARNING"
