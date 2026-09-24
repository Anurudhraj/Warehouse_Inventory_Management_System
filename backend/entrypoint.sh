#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# Container entrypoint: wait for backing services, apply migrations,
# collect static files, then hand over to the requested command
# (gunicorn web server, or Celery worker/beat for the worker services).
# ----------------------------------------------------------------------------
set -euo pipefail

wait_for() {
    local host="$1" port="$2" name="$3" retries="${4:-30}"
    echo "Waiting for ${name} at ${host}:${port} ..."
    for _ in $(seq 1 "${retries}"); do
        if python -c "
import socket, sys
sock = socket.create_connection(('${host}', ${port}), timeout=2)
sock.close()
" 2>/dev/null; then
            echo "${name} is up."
            return 0
        fi
        sleep 2
    done
    echo "ERROR: ${name} at ${host}:${port} did not become ready in time." >&2
    exit 1
}

CMD_NAME="$(basename "${1:-gunicorn}")"

DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"

case "${CMD_NAME}" in
    gunicorn)
        wait_for "${DB_HOST}" "${DB_PORT}" "PostgreSQL"
        wait_for "${REDIS_HOST:-redis}" "${REDIS_PORT:-6379}" "Redis"
        echo "Applying database migrations ..."
        python manage.py migrate --noinput
        echo "Collecting static files ..."
        python manage.py collectstatic --noinput
        ;;
    celery)
        wait_for "${REDIS_HOST:-redis}" "${REDIS_PORT:-6379}" "Redis"
        ;;
esac

exec "$@"
