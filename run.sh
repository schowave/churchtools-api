# Build the Docker image
docker build -t schowave/churchtools .

# Run the Docker container
docker run -p 5005:5000 schowave/churchtools
