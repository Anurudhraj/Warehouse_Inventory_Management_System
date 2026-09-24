"""Base Django settings shared by all environments.

Environment-specific behaviour lives in ``development.py`` /
``production.py``. All secrets are read from environment variables —
never hard-code them (see ``.env.example``).
"""

from pathlib import Path

from config import env

# ---------------------------------------------------------------------------
# Paths & environment
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]

# "development" | "production" | "test" — set by the settings module in use.
ENVIRONMENT: str = env.env_str("DJANGO_ENV", default="development")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env.env_str("DJANGO_SECRET_KEY", default="")

DEBUG = env.env_bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env.env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "[::1]"],
)

CSRF_TRUSTED_ORIGINS = env.env_list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# ---------------------------------------------------------------------------
# Application definition — domain modules
# ---------------------------------------------------------------------------
# Single source of truth for the business modules. Each module is a Django
# app under ``apps/`` and is mounted at ``/api/v1/<module>/`` by
# ``config.api_urls``. Business logic is added in later parts of the plan.
DOMAIN_MODULES = [
    "identity",
    "organizations",
    "warehouses",
    "products",
    "pricing",
    "suppliers",
    "procurement",
    "receiving",
    "locations",
    "putaway",
    "inventory",
    "transfers",
    "orders",
    "fulfillment",
    "replenishment",
    "stock_counts",
    "returns",
    "barcode",
    "rfid",
    "reports",
    "notifications",
    "integrations",
    "audit",
    "security",
    "configuration",
]

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "corsheaders",
]

LOCAL_APPS = ["apps.core"] + [f"apps.{module}" for module in DOMAIN_MODULES]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.RequestContextMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Rejects requests whose tracked session was revoked (logout-all, admin
    # revocation, password reset). Runs after auth so request.user is known.
    "apps.identity.middleware.SessionRevocationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.AccessLogMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database — PostgreSQL (never exposed publicly; see docker-compose.yml)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.env_str("POSTGRES_DB", default="wims"),
        "USER": env.env_str("POSTGRES_USER", default="wims"),
        "PASSWORD": env.env_str("POSTGRES_PASSWORD", default=""),
        "HOST": env.env_str("POSTGRES_HOST", default="localhost"),
        "PORT": env.env_str("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": env.env_int("POSTGRES_CONN_MAX_AGE", default=60),
    }
}

# ---------------------------------------------------------------------------
# Cache — Redis (never exposed publicly; see docker-compose.yml)
# ---------------------------------------------------------------------------
REDIS_URL = env.env_str("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
        },
        "KEY_PREFIX": "wims",
    }
}

# ---------------------------------------------------------------------------
# Celery (broker defaults derive from REDIS_URL unless overridden)
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env.env_str("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env.env_str("CELERY_RESULT_BACKEND", default="")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ---------------------------------------------------------------------------
# Auth & sessions
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "identity.User"

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

# Argon2id is the preferred password hash; Django's PBKDF2 stays as fallback
# for existing hashes and remains available for rotation.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = env.env_int("SESSION_COOKIE_AGE", default=8 * 60 * 60)  # 8 hours
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ---------------------------------------------------------------------------
# Authentication hardening (identity + security modules)
# ---------------------------------------------------------------------------
# Account lockout after repeated failures (per account) …
AUTH_MAX_FAILED_ATTEMPTS = env.env_int("AUTH_MAX_FAILED_ATTEMPTS", default=5)
AUTH_LOCKOUT_SECONDS = env.env_int("AUTH_LOCKOUT_SECONDS", default=15 * 60)
# … and per-IP throttling at the API layer (DRF scoped throttles).
AUTH_LOGIN_THROTTLE_RATE = env.env_str("AUTH_LOGIN_THROTTLE_RATE", default="10/min")
AUTH_PASSWORD_RESET_THROTTLE_RATE = env.env_str(
    "AUTH_PASSWORD_RESET_THROTTLE_RATE", default="5/hour"
)
AUTH_EMAIL_THROTTLE_RATE = env.env_str("AUTH_EMAIL_THROTTLE_RATE", default="5/hour")
AUTH_MFA_THROTTLE_RATE = env.env_str("AUTH_MFA_THROTTLE_RATE", default="10/min")

# Token lifetimes (seconds)
AUTH_PASSWORD_RESET_TTL = env.env_int("AUTH_PASSWORD_RESET_TTL", default=60 * 60)
AUTH_EMAIL_VERIFICATION_TTL = env.env_int("AUTH_EMAIL_VERIFICATION_TTL", default=24 * 60 * 60)
AUTH_MFA_CHALLENGE_TTL = env.env_int("AUTH_MFA_CHALLENGE_TTL", default=5 * 60)

# When true, unverified accounts cannot complete login.
AUTH_REQUIRE_EMAIL_VERIFICATION = env.env_bool("AUTH_REQUIRE_EMAIL_VERIFICATION", default=False)
# When true, platform administrators must have a confirmed MFA device to log in.
AUTH_REQUIRE_MFA_FOR_ADMINS = env.env_bool("AUTH_REQUIRE_MFA_FOR_ADMINS", default=True)

# TOTP parameters (RFC 6238) and MFA device limits
AUTH_MFA_ISSUER = env.env_str("AUTH_MFA_ISSUER", default="WIMS")
AUTH_MFA_VALID_WINDOW = env.env_int("AUTH_MFA_VALID_WINDOW", default=1)  # ±1 step (±30 s)
AUTH_MFA_RECOVERY_CODE_COUNT = env.env_int("AUTH_MFA_RECOVERY_CODE_COUNT", default=10)

# Tracked sessions: idle timeout used by the session management endpoints.
SESSION_IDLE_TIMEOUT = env.env_int("SESSION_IDLE_TIMEOUT", default=8 * 60 * 60)

# ---------------------------------------------------------------------------
# Email (password reset, email verification, notifications)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env.env_str(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env.env_str("EMAIL_HOST", default="")
EMAIL_PORT = env.env_int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env.env_str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env.env_str("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.env_bool("EMAIL_USE_TLS", default=True)
EMAIL_TIMEOUT = env.env_int("EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env.env_str("DEFAULT_FROM_EMAIL", default="no-reply@wims.local")
SERVER_EMAIL = env.env_str("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
# Public base URL used to build links inside emails (reset/verify).
FRONTEND_BASE_URL = env.env_str("FRONTEND_BASE_URL", default="http://localhost:5173")

# ---------------------------------------------------------------------------
# API — Django REST Framework, versioning & OpenAPI
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.identity.authentication.SessionAuthenticationWithChallenge",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",  # tightened in Part 2 (identity module)
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        # Every list endpoint declares ``search_fields``/``ordering_fields``;
        # enabling the backends globally is what makes those declarations real.
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ("v1",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": AUTH_LOGIN_THROTTLE_RATE,
        "password_reset": AUTH_PASSWORD_RESET_THROTTLE_RATE,
        "email": AUTH_EMAIL_THROTTLE_RATE,
        "mfa": AUTH_MFA_THROTTLE_RATE,
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Warehouse & Inventory Management System API",
    "DESCRIPTION": (
        "Multi-warehouse inventory management platform. "
        "Part 1 delivers the API foundation; business modules are added "
        "in subsequent parts."
    ),
    "VERSION": "v1",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+",
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "COMPONENT_SPLIT_REQUEST": True,
}

# ---------------------------------------------------------------------------
# CORS — explicit origin allow-list only (no wildcards)
# ---------------------------------------------------------------------------
# Empty by default: each environment must state its origins explicitly.
# (development.py adds the local Vite origins; production.py refuses to start
# without them.)
CORS_ALLOWED_ORIGINS = env.env_list("CORS_ALLOWED_ORIGINS", default=[])
# Swagger/ReDoc UIs: on in development, off in production unless enabled.
ENABLE_API_DOCS = env.env_bool("ENABLE_API_DOCS", default=True)
CORS_ALLOWED_ORIGIN_REGEXES = env.env_list("CORS_ALLOWED_ORIGIN_REGEXES", default=[])
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Security defaults (strengthened in production.py)
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_BROWSER_XSS_FILTER = True

# ---------------------------------------------------------------------------
# I18N
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Logging — console + optional file, sensitive values are redacted
# ---------------------------------------------------------------------------
LOG_LEVEL = env.env_str("LOG_LEVEL", default="INFO").upper()
LOG_DIR = env.env_str("LOG_DIR", default="")

_handlers = ["console"]
if LOG_DIR:
    _handlers.append("file")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "sensitive_data": {"()": "apps.core.logging.SensitiveDataFilter"},
        "request_context": {"()": "apps.core.logging.RequestContextFilter"},
    },
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name} [{request_id}] {message}",
            "style": "{",
        },
        "access": {
            "format": "[ACCESS] {asctime} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["sensitive_data", "request_context"],
        },
        **(
            {
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": f"{LOG_DIR}/wims.log",
                    "maxBytes": 10 * 1024 * 1024,
                    "backupCount": 5,
                    "formatter": "verbose",
                    "filters": ["sensitive_data", "request_context"],
                }
            }
            if LOG_DIR
            else {}
        ),
    },
    "root": {
        "handlers": _handlers,
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": _handlers,
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": _handlers,
            "level": "WARNING",
            "propagate": False,
        },
        "django.security": {
            "handlers": _handlers,
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": _handlers,
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "access": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
