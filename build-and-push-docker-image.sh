VERSION=0.0.27

# Build the Docker image
docker build -t schowave/churchtools:$VERSION .

# Push the docker image
docker push schowave/churchtools:$VERSION
