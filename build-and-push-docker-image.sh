#!/bin/bash

VERSION=1.4.4

echo "Running tests before building the Docker image..."
# Run the tests and store the exit code
python -m pytest
TEST_EXIT_CODE=$?

# Check if tests passed
if [ $TEST_EXIT_CODE -eq 0 ]; then
    # Now set -e to exit on error for the build and push steps
    set -e  # Exit immediately if a command exits with a non-zero status
    echo "Tests passed successfully. Building Docker image..."
    
    # Build the Docker image
    docker build -t schowave/churchtools:$VERSION .
    
    # Push the docker image
    echo "Pushing Docker image to registry..."
    docker push schowave/churchtools:$VERSION
    
    echo "Docker image schowave/churchtools:$VERSION built and pushed successfully."
else
    echo "Tests failed. Docker image will not be built."
    exit 1
fi
