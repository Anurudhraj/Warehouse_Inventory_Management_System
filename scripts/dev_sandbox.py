#!/usr/bin/env python
"""Bootstrap everything the Browser preview needs, without Docker.

The preview pane is an *embedded* (cross-site) client: the browser may refuse to
send ``SameSite=Lax`` cookies on the API calls the SPA makes, which looks exactly
like "the password is right but I keep landing back on the sign-in page". This
script therefore:

1. starts the embedded PostgreSQL + Redis servers (``pgserver`` / ``redislite``);
2. writes ``backend/.env`` with development settings that work in an embed
   (``SameSite=None; Secure`` cookies plus the opt-in bearer fallback);
3. migrates the database, syncs the RBAC registry and seeds demo data;
4. keeps running so the services stay available (Ctrl+C to stop).

Usage::

    .venv/bin/python scripts/dev_sandbox.py            # start services + prepare data
    .venv/bin/python scripts/dev_sandbox.py --no-seed  # skip the demo dataset

For a *local* (non-embedded) development loop you do not need the relaxed cookie
settings — ``SameSite=Lax`` cookies are the stronger default and are used
everywhere except when this script writes them into ``.env``.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / ".devdata"
PGDATA = DATA_DIR / "pgdata"
REDIS_DB = DATA_DIR / "redis.db"
BACKEND = REPO_ROOT / "backend"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"

DEV_ENV = """\
# Local development environment (written by scripts/dev_sandbox.py).
DJANGO_ENV=development
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=dev-only-secret-key-not-for-production-0123456789abcdef
POSTGRES_DB=wims
POSTGRES_USER=wims
POSTGRES_HOST={pg_host}
POSTGRES_PORT=5432
POSTGRES_PASSWORD=
REDIS_URL=redis://127.0.0.1:6379/0
LOG_LEVEL=INFO

# --- embedded (cross-site) preview support ---------------------------------
# ``SameSite=None; Secure`` so the browser sends the session cookie from inside
# a cross-site iframe; ``AUTH_ENABLE_TOKEN_FALLBACK`` adds the bearer fallback
# for browsers that block third-party cookies outright.
DJANGO_COOKIE_SAMESITE=None
DJANGO_COOKIE_SECURE=true
AUTH_ENABLE_TOKEN_FALLBACK=true
"""


def start_postgres() -> str:
    import pgserver

    server = pgserver.get_server(PGDATA, cleanup_mode=None)
    server.ensure_postgres_running()
    uri = server.get_uri()
    host = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query).get("host", ["/tmp"])[0]

    def sql(statement: str) -> str:
        return server.psql(statement + ";\n")

    if "wims" not in sql("select rolname from pg_roles"):
        sql("create role wims login createdb")
    if "wims" not in sql("select datname from pg_database"):
        sql("create database wims owner wims")
    print(f"[postgres] ready (socket {host})", flush=True)
    return host


def start_redis() -> None:
    from redislite import Redis

    redis = Redis(REDIS_DB, serverconfig={"port": "6379", "bind": "127.0.0.1"})
    print(f"[redis] ready (ping={redis.ping()})", flush=True)


def write_env(pg_host: str) -> None:
    (BACKEND / ".env").write_text(DEV_ENV.format(pg_host=pg_host))
    print("[env] wrote backend/.env", flush=True)


def manage(*args: str, check: bool = True) -> int:
    python = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
    result = subprocess.run(
        [str(python), "manage.py", *args], cwd=BACKEND, check=False, text=True
    )
    if check and result.returncode != 0:
        raise SystemExit(f"manage.py {' '.join(args)} failed ({result.returncode})")
    return result.returncode


def prepare_data(seed: bool) -> None:
    manage("migrate", "--noinput")
    manage("sync_rbac")
    manage(
        "create_platform_admin",
        "--email",
        "dev-admin@wims.local",
        "--first-name",
        "Dev",
        "--last-name",
        "Admin",
        "--password",
        os.environ.get("WIMS_DEV_ADMIN_PASSWORD", "Dev-Only-Passw0rd-2026!"),
    )
    if seed:
        manage("seed_demo_data")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-seed", action="store_true", help="skip demo data")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="start services, prepare the database, then exit",
    )
    options = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    pg_host = start_postgres()
    start_redis()
    write_env(pg_host)
    prepare_data(seed=not options.no_seed)

    print(
        "\nReady.\n"
        "  API   : python manage.py runserver 0.0.0.0:8000\n"
        "  Client: cd frontend && npx vite --host 0.0.0.0\n"
        "  Sign in: dev-admin@wims.local / Dev-Only-Passw0rd-2026!  (platform admin)\n"
        "  Demo   : manager@wims.local, controller@wims.local, operator@wims.local,\n"
        "           viewer@wims.local — password Wims-Demo-Password-2026!\n",
        flush=True,
    )

    if options.prepare_only:
        return 0

    stop = False

    def handle(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    while not stop:
        time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
