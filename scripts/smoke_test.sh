#!/bin/sh
# Start the built image and check that it serves health, the rendered login page, and static files.
# Usage: IMAGE=churchtools-local scripts/smoke_test.sh   (mise run smoke)
set -eu

IMAGE="${IMAGE:-churchtools-local}"
if [ -n "${CONTAINER_ENGINE:-}" ]; then
    ENGINE="$CONTAINER_ENGINE"
elif command -v podman >/dev/null 2>&1; then
    ENGINE=podman
else
    ENGINE=docker
fi
PORT="${SMOKE_PORT:-5099}"
NAME="churchtools-smoke-$$"
BASE="http://localhost:$PORT"

cleanup() { "$ENGINE" rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

fail() {
    echo "SMOKE TEST FAILED: $1" >&2
    "$ENGINE" logs "$NAME" 2>&1 | tail -40 >&2 || true
    exit 1
}

"$ENGINE" run -d --name "$NAME" -p "$PORT:5005" -e CHURCHTOOLS_BASE=smoke-test.invalid "$IMAGE" >/dev/null

i=0
until curl -sf "$BASE/health" >/dev/null 2>&1; do
    i=$((i + 1))
    [ "$i" -ge 30 ] && fail "/health not reachable after 30s"
    sleep 1
done

curl -sf "$BASE/health" | grep -q '"status":"ok"' || fail "/health did not report ok"
curl -sf "$BASE/" | grep -q 'name="_csrf_token" value="[^"]' || fail "login page did not render with a CSRF token"
curl -sf -o /dev/null "$BASE/static/js/events.js" || fail "static files not served"

"$ENGINE" exec "$NAME" grep -q '^Uid:[[:space:]]*0[[:space:]]' /proc/1/status && fail "app runs as root"

echo "Smoke test passed ($IMAGE via $ENGINE)"
