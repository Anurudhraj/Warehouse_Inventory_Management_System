"""Environment variable access helpers.

Secrets and deployment-specific configuration are *always* provided via
environment variables (see ``.env.example``). Nothing sensitive may be
hard-coded in this repository.

For local development a ``.env`` file is supported (never commit it):
lookup order is process environment > ``backend/.env`` > repo-root ``.env``.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

_LOADED_DOTENV = False


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env parser (KEY=VALUE, ``#`` comments, optional quotes)."""
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value.startswith("export "):
            value = value[len("export ") :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    return values


def _load_dotenv_once() -> None:
    """Populate ``os.environ`` from .env files without overriding it.

    Set ``WIMS_LOAD_DOTENV=false`` to disable .env loading entirely (used by
    the settings-hardening tests and by deployments where the environment is
    the single source of truth).
    """
    global _LOADED_DOTENV
    if _LOADED_DOTENV:
        return
    _LOADED_DOTENV = True
    if (os.environ.get("WIMS_LOAD_DOTENV") or "").strip().lower() in ("0", "false", "no", "off"):
        return
    candidates = [BASE_DIR / ".env", BASE_DIR.parent / ".env"]
    for candidate in reversed(candidates):  # repo root has lowest priority
        for key, value in _parse_dotenv(candidate).items():
            os.environ.setdefault(key, value)


def get_raw(name: str, default: str | None = None, required: bool = False) -> str | None:
    _load_dotenv_once()
    value = os.environ.get(name)
    if value is None or value == "":
        if required:
            raise RuntimeError(
                f"Required environment variable '{name}' is not set. "
                "See .env.example for the full list."
            )
        return default
    return value


def env_str(name: str, default: str = "", required: bool = False) -> str:
    value = get_raw(name, required=required)
    return default if value is None else value


def env_bool(name: str, default: bool = False) -> bool:
    value = get_raw(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on", "y")


def env_int(name: str, default: int = 0) -> int:
    value = get_raw(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable '{name}' must be an integer, got {value!r}"
        ) from exc


def env_list(
    name: str,
    default: list[str] | None = None,
    separator: str = ",",
    required: bool = False,
) -> list[str]:
    value = get_raw(name, required=required)
    if value is None or not value.strip():
        if required and not default:
            raise RuntimeError(
                f"Required environment variable '{name}' is not set. "
                "See .env.example for the full list."
            )
        return list(default or [])
    return [item.strip() for item in value.split(separator) if item.strip()]


def env_choice(name: str, default: str, allowed: tuple[str, ...]) -> str:
    value = env_str(name, default=default)
    if value not in allowed:
        raise RuntimeError(f"Environment variable '{name}' must be one of {allowed}, got {value!r}")
    return value
