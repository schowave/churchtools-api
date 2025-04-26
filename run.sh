# Build the Docker image
docker build -t schowave/churchtools .

# Run the Docker container
docker run -p 5005:5005 -v .:/app/data schowave/churchtools
