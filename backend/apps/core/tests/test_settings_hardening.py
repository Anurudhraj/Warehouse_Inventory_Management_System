"""Settings hardening tests — the production module must fail fast."""

import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BACKEND_DIR = Path(__file__).resolve().parents[3]


def _run_settings_check(settings_module: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    """Load a settings module in a fresh interpreter and report success."""
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "DJANGO_SETTINGS_MODULE": settings_module,
        # Ignore any local .env so each test controls the full configuration.
        "WIMS_LOAD_DOTENV": "false",
        **env,
    }
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup(); print('ok')"],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


BASE_PROD_ENV = {
    "DJANGO_SECRET_KEY": "x" * 64,
    "DJANGO_ALLOWED_HOSTS": "wims.example.com",
    "CORS_ALLOWED_ORIGINS": "https://wims.example.com",
    "DJANGO_CSRF_TRUSTED_ORIGINS": "https://wims.example.com",
    "POSTGRES_PASSWORD": "unit-test-password",
}


class ProductionSettingsTests(SimpleTestCase):
    def test_production_settings_load_with_complete_configuration(self):
        result = _run_settings_check("config.settings.production", BASE_PROD_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_settings_reject_missing_secret_key(self):
        result = _run_settings_check(
            "config.settings.production", {**BASE_PROD_ENV, "DJANGO_SECRET_KEY": ""}
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_production_settings_reject_debug_mode(self):
        result = _run_settings_check(
            "config.settings.production", {**BASE_PROD_ENV, "DJANGO_DEBUG": "true"}
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_DEBUG must be false", result.stderr)

    def test_production_settings_require_explicit_cors_origins(self):
        result = _run_settings_check(
            "config.settings.production", {**BASE_PROD_ENV, "CORS_ALLOWED_ORIGINS": ""}
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CORS_ALLOWED_ORIGINS", result.stderr)

    def test_production_settings_require_allowed_hosts(self):
        result = _run_settings_check(
            "config.settings.production", {**BASE_PROD_ENV, "DJANGO_ALLOWED_HOSTS": ""}
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS", result.stderr)
