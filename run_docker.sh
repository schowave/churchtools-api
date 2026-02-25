#!/bin/bash
set -e

IMAGE=schowave/churchtools

# Detect container engine: prefer podman, fall back to docker
if command -v podman &> /dev/null; then
    ENGINE=podman
elif command -v docker &> /dev/null; then
    ENGINE=docker
else
    echo "Error: Neither podman nor docker found. Please install one of them."
    exit 1
fi

echo "Using $ENGINE to build and run..."

$ENGINE build -t "$IMAGE" .
$ENGINE run -p 5005:5005 -v ./data:/app/data --env-file .env "$IMAGE"
