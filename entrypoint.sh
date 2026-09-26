#!/bin/sh
set -e

DB_FILE="${DB_PATH:-/app/data/churchtools.db}"

# Ensure data directory exists
mkdir -p "$(dirname "$DB_FILE")"

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

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port 5005 "$@"
