#!/usr/bin/env bash
set -euo pipefail

child_pid=""

on_signal() {
  echo "Received shutdown signal, exiting."
  if [ -n "$child_pid" ]; then
    kill -TERM "$child_pid" 2>/dev/null || true
  fi
  exit 1
}
trap on_signal INT TERM

wait_for_db() {
  echo "Waiting for database to accept connections..."
  python - <<'PYEOF' &
import os
import sys
import time

import dj_database_url
import psycopg2

db_config = dj_database_url.parse(os.environ["DATABASE_URL"])

timeout = 30
interval = 1
elapsed = 0

while elapsed < timeout:
    try:
        conn = psycopg2.connect(
            dbname=db_config["NAME"],
            user=db_config["USER"],
            password=db_config["PASSWORD"],
            host=db_config["HOST"],
            port=db_config["PORT"],
            connect_timeout=3,
        )
        conn.close()
        print("Database is accepting connections.")
        sys.exit(0)
    except psycopg2.OperationalError as exc:
        print(f"Database not ready yet ({exc.__class__.__name__}), retrying...")
        time.sleep(interval)
        elapsed += interval

print(f"Database did not become available within {timeout}s.", file=sys.stderr)
sys.exit(1)
PYEOF
  child_pid=$!
  wait "$child_pid"
}

wait_for_db

if [ "${1:-}" = "gunicorn" ]; then
  echo "Running migrations (api container)..."
  python manage.py migrate --noinput
else
  echo "Skipping migrations — not the api container (assumes migrations already applied)."
fi

exec "$@"