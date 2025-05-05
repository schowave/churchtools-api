#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting test execution in Docker...${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker and try again.${NC}"
    exit 1
fi

# Docker image name
IMAGE_NAME="churchtools-api-test"

# Temporary file to store the hash of source files
HASH_FILE=".docker_source_hash"

# Function to calculate hash of source files
calculate_source_hash() {
    find . -type f \( -name "*.py" -o -name "*.sh" -o -name "Dockerfile" -o -name "*.html" -o -name "*.css" -o -name "*.js" -o -name "requirements*.txt" \) -not -path "*/\.*" | sort | xargs cat 2>/dev/null | md5sum | cut -d ' ' -f 1
}

# Calculate current source hash
CURRENT_HASH=$(calculate_source_hash)

# Check if we need to rebuild the image
REBUILD=false

# Check if the image already exists
if [[ "$(docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]]; then
    echo -e "${YELLOW}Docker image does not exist. Creating new image...${NC}"
    REBUILD=true
else
    # Check if hash file exists and if the hash has changed
    if [ ! -f "$HASH_FILE" ] || [ "$(cat $HASH_FILE)" != "$CURRENT_HASH" ]; then
        echo -e "${YELLOW}Source files have changed. Rebuilding Docker image...${NC}"
        REBUILD=true
    else
        echo -e "${GREEN}Docker image $IMAGE_NAME exists and source files haven't changed.${NC}"
    fi
fi

# Build the image if needed
if [ "$REBUILD" = true ]; then
    # Build Docker image from existing Dockerfile
    docker build -t $IMAGE_NAME .
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error creating Docker image.${NC}"
        exit 1
    fi
    
    # Save the new hash
    echo "$CURRENT_HASH" > "$HASH_FILE"
    echo -e "${GREEN}Docker image built successfully.${NC}"
fi

echo -e "${YELLOW}Running tests in Docker...${NC}"

# Run tests in Docker with overridden CMD command
docker run --rm \
    -e PYTHONPATH=/app \
    -e CHURCHTOOLS_BASE=test.church.tools \
    -e DB_PATH=:memory: \
    $IMAGE_NAME \
    python -m pytest tests/ -v

# Check if the tests were successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}All tests were executed successfully!${NC}"
else
    echo -e "${RED}Some tests have failed.${NC}"
    exit 1
fi