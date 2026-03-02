#!/bin/bash
set -e

IMAGE_NAME="churchtools-local"
CONTAINER_NAME="churchtools-local"
PORT=5005
DATA_DIR="$(pwd)/data"

# Ensure the data directory exists for the SQLite database
mkdir -p "$DATA_DIR"

# Stop and remove existing container if running
if podman ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping existing container..."
    podman stop "$CONTAINER_NAME" 2>/dev/null || true
    podman rm "$CONTAINER_NAME" 2>/dev/null || true
fi

echo "Building container image..."
podman build -t "$IMAGE_NAME" .

echo "Starting container on http://localhost:${PORT}"
podman run \
    --name "$CONTAINER_NAME" \
    --env-file .env \
    -e DB_PATH=/app/data/churchtools.db \
    -p "${PORT}:5005" \
    -v "${DATA_DIR}:/app/data" \
    --rm \
    "$IMAGE_NAME"
