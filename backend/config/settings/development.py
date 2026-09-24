"""Development settings — relaxed defaults for a fast local loop.

Never run production traffic with this module; it is intended for local
machines and the sandboxed dev server only.
"""

import warnings

from .base import *
from .base import env

ENVIRONMENT = "development"

DEBUG = env.env_bool("DJANGO_DEBUG", default=True)

if not SECRET_KEY:
    SECRET_KEY = "insecure-development-only-key-change-me"
    warnings.warn(
        "DJANGO_SECRET_KEY is not set; using an insecure development key.",
        stacklevel=2,
    )

# Accept the sandbox/preview hosts in development; override via env.
ALLOWED_HOSTS = env.env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=[
        "localhost",
        "127.0.0.1",
        "0.0.0.0",  # noqa: S104 - dev server binds all interfaces
        "[::1]",
        ".localhost",
        ".e2b.app",
    ],
)

CSRF_TRUSTED_ORIGINS = env.env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[],
)

# Local frontend origins (Vite dev/preview servers) — applied in development
# only. Base settings ship an empty allow-list so no environment inherits
# localhost origins by accident.
CORS_ALLOWED_ORIGINS = env.env_list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
)

# Verbose logging in development (override with LOG_LEVEL).
_dev_log_level = env.env_str("LOG_LEVEL", default="DEBUG")
LOGGING["root"]["level"] = _dev_log_level
LOGGING["loggers"]["apps"]["level"] = _dev_log_level
