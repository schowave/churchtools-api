#!/bin/bash

set -e

IMAGE=schowave/churchtools

# Read version from pyproject.toml (single source of truth)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('${SCRIPT_DIR}/pyproject.toml','rb'))['project']['version'])")

echo "Aktuelle Version in pyproject.toml: ${VERSION}"
read -r -p "Mit dieser Version deployen? (j=ja / neue Version eingeben): " answer

if [ "$answer" != "j" ] && [ "$answer" != "ja" ]; then
    if [ -z "$answer" ]; then
        echo "Abgebrochen."
        exit 0
    fi
    VERSION="$answer"
    # Update pyproject.toml with new version
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

echo "Using $ENGINE to build and push multi-architecture image..."

if [ "$ENGINE" = "podman" ]; then
    # Build for each platform
    podman build --build-arg APP_VERSION=${VERSION} --platform linux/amd64 -t ${IMAGE}:${VERSION}-amd64 .
    podman build --build-arg APP_VERSION=${VERSION} --platform linux/arm64 -t ${IMAGE}:${VERSION}-arm64 .

    # Create and push versioned manifest
    podman manifest rm ${IMAGE}:${VERSION} 2>/dev/null || true
    podman manifest create ${IMAGE}:${VERSION}
    podman manifest add ${IMAGE}:${VERSION} ${IMAGE}:${VERSION}-amd64
    podman manifest add ${IMAGE}:${VERSION} ${IMAGE}:${VERSION}-arm64
    podman manifest push ${IMAGE}:${VERSION} docker://docker.io/${IMAGE}:${VERSION}

    # Create and push latest manifest
    podman manifest rm ${IMAGE}:latest 2>/dev/null || true
    podman manifest create ${IMAGE}:latest
    podman manifest add ${IMAGE}:latest ${IMAGE}:${VERSION}-amd64
    podman manifest add ${IMAGE}:latest ${IMAGE}:${VERSION}-arm64
    podman manifest push ${IMAGE}:latest docker://docker.io/${IMAGE}:latest
else
    # Docker buildx multi-arch build
    docker buildx create --use --name multi-platform-builder || true
    docker buildx build --build-arg APP_VERSION=${VERSION} --platform linux/amd64,linux/arm64 \
        --tag ${IMAGE}:${VERSION} --tag ${IMAGE}:latest --push .
fi

echo "${IMAGE}:${VERSION} and ${IMAGE}:latest built and pushed successfully."
