VERSION=1.5.1

# Build the Docker image
docker build --platform=linux/amd64 -t schowave/churchtools:$VERSION .

docker tag schowave/churchtools:$VERSION schowave/churchtools:latest

# Push the docker image
docker push schowave/churchtools:$VERSION
docker push schowave/churchtools:latest