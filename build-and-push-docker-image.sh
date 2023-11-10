VERSION=0.0.26

# Build the Docker image
docker build -t schowave/churchtools:$VERSION .

# Push the docker image
docker push schowave/churchtools:$VERSION
