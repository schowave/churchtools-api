#!/bin/sh
set -e

DB_FILE="${DB_PATH:-/app/data/churchtools.db}"

# Ensure data directory exists
mkdir -p "$(dirname "$DB_FILE")"

# Started as root: hand the data directory to the app user and re-run this script without root.
# Volumes from releases that ran as root are owned by root, so the chown keeps them writable.
if [ "$(id -u)" = "0" ]; then
    chown -R app:app "$(dirname "$DB_FILE")"
    exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
fi

# If DB exists with app tables but no alembic_version, stamp it as the initial schema
if [ -f "$DB_FILE" ]; then
    HAS_APP_TABLES=$(sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='table' AND name='color_settings'" 2>/dev/null || true)
    HAS_ALEMBIC=$(sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'" 2>/dev/null || true)

    if [ -n "$HAS_APP_TABLES" ] && [ -z "$HAS_ALEMBIC" ]; then
        # Pre-alembic databases match the initial schema (001); later migrations still run below
        echo "Existing database detected without alembic tracking. Stamping as 001..."
        alembic stamp 001
    fi
fi

# Run migrations
alembic upgrade head

# Start the application. Behind a reverse proxy set FORWARDED_ALLOW_IPS (read by uvicorn) to the
# proxy's address, so client IPs (login rate limit) and https (secure cookies, HSTS) are detected.
exec uvicorn app.main:app --host 0.0.0.0 --port 5005 --proxy-headers "$@"
