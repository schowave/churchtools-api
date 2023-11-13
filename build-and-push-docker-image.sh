VERSION=0.4.0

# Build the Docker image
docker build -t schowave/churchtools:$VERSION .

# Push the docker image
docker push schowave/churchtools:$VERSION
