#!/bin/bash

set -e

IMAGE=schowave/churchtools

# Read version from pyproject.toml (single source of truth)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CURRENT=$(python3 -c "import tomllib; print(tomllib.load(open('${SCRIPT_DIR}/pyproject.toml','rb'))['project']['version'])")
NEXT=$(python3 -c "v='${CURRENT}'.split('.'); v[-1]=str(int(v[-1])+1); print('.'.join(v))")

echo "Aktuelle Version: ${CURRENT}"
read -r -p "Welche Version deployen? [${NEXT}]: " answer

VERSION="${answer:-$NEXT}"

if [ "$VERSION" != "$CURRENT" ]; then
    sed -i '' "s/^version = \".*\"/version = \"${VERSION}\"/" "${SCRIPT_DIR}/pyproject.toml"
    echo "Version in pyproject.toml auf ${VERSION} aktualisiert."
fi

# Detect container engine: prefer podman, fall back to docker
if command -v podman &> /dev/null; then
    ENGINE=podman
elif command -v docker &> /dev/null; then
    ENGINE=docker
else
    echo "Error: Neither podman nor docker found. Please install one of them."
    exit 1
fi

# Ensure we're logged in to Docker Hub
if ! $ENGINE login --get-login docker.io &> /dev/null; then
    echo "Not logged in to Docker Hub. Please log in:"
    $ENGINE login docker.io
fi

echo "Using $ENGINE to build and push image..."

if [ "$ENGINE" = "podman" ]; then
    podman build --platform linux/amd64 -t ${IMAGE}:${VERSION} .
    podman push ${IMAGE}:${VERSION} docker://docker.io/${IMAGE}:${VERSION}
    podman tag ${IMAGE}:${VERSION} ${IMAGE}:latest
    podman push ${IMAGE}:latest docker://docker.io/${IMAGE}:latest
else
    docker build --tag ${IMAGE}:${VERSION} --tag ${IMAGE}:latest .
    docker push ${IMAGE}:${VERSION}
    docker push ${IMAGE}:latest
fi

echo "${IMAGE}:${VERSION} and ${IMAGE}:latest built and pushed successfully."
