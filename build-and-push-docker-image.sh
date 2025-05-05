#!/bin/bash

VERSION=2.10.0

# Set -e to exit on error for the build and push steps
set -e  # Exit immediately if a command exits with a non-zero status
echo "Building Docker image..."

# Build and push multi-architecture Docker image
echo "Building and pushing multi-architecture Docker image..."
docker buildx create --use --name multi-platform-builder || true
docker buildx build --platform linux/amd64,linux/arm64 --tag schowave/churchtools:$VERSION --tag schowave/churchtools:latest --push .

echo "Docker image schowave/churchtools:$VERSION and schowave/churchtools:latest built and pushed successfully."
