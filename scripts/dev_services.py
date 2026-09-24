#!/usr/bin/env python
"""Start embedded PostgreSQL + Redis for local development.

Useful on machines without Docker: it downloads/uses bundled server
binaries via ``pgserver`` and ``redislite`` (see requirements-dev.txt)
and keeps them running until the process is stopped.

    python scripts/dev_services.py

Environment variables produced (export them or write them to backend/.env):

    POSTGRES_HOST/PORT/USER/DB
    REDIS_URL
"""
from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / ".devdata"
DATA_DIR.mkdir(exist_ok=True)

PGDATA = DATA_DIR / "pgdata"
REDIS_DB = DATA_DIR / "redis.db"


def start_postgres() -> dict[str, str]:
    import pgserver

    server = pgserver.get_server(PGDATA, cleanup_mode=None)
    server.ensure_postgres_running()
    uri = server.get_uri().replace("postgresql://", "postgresql://")
    # pgserver URI looks like: postgresql://user@/dbname?host=/tmp/xxx
    print(f"[postgres] {uri}", flush=True)
    return {"uri": uri, "server": server}


def start_redis() -> dict[str, str]:
    from redislite import Redis

    redis = Redis(REDIS_DB)
    print(f"[redis] {redis.connection_pool.connection_kwargs}", flush=True)
    return {"url": f"unix://{REDIS_DB}"}


def main() -> int:
    pg = start_postgres()
    redis = start_redis()

    print("\nExport these for the backend:", flush=True)
    print(f"  POSTGRES_URI={pg['uri']}", flush=True)
    print(f"  REDIS_URL={redis['url']}", flush=True)
    print("\nServices running. Press Ctrl+C to stop.", flush=True)

    stop = False

    def handle(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    while not stop:
        time.sleep(1)

    print("Shutting down ...", flush=True)
    os.environ["PATH"] = os.environ.get("PATH", "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
