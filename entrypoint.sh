#!/bin/sh
set -e

DB_FILE="${DB_PATH:-/app/data/churchtools.db}"

# Ensure data directory exists
mkdir -p "$(dirname "$DB_FILE")"

# If DB exists with app tables but no alembic_version, stamp it as current
if [ -f "$DB_FILE" ]; then
    HAS_APP_TABLES=$(sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='table' AND name='color_settings'" 2>/dev/null || true)
    HAS_ALEMBIC=$(sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'" 2>/dev/null || true)

    if [ -n "$HAS_APP_TABLES" ] && [ -z "$HAS_ALEMBIC" ]; then
        echo "Existing database detected without alembic tracking. Stamping as current..."
        alembic stamp head
    fi
fi

# Run migrations
alembic upgrade head

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port 5005 "$@"
