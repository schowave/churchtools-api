#!/bin/bash

set -e  # Exit on error

echo "=== ChurchTools API Docker Setup ==="
echo ""

# Create data directory if it doesn't exist
echo "Erstelle data-Verzeichnis..."
mkdir -p ./data
chmod 777 ./data  # Ensure write permissions

# Check if container already exists
CONTAINER_EXISTS=$(docker ps -a -q --filter "name=churchtools-api")
if [ -n "$CONTAINER_EXISTS" ]; then
    echo "Container existiert bereits. Stoppe und entferne ihn..."
    docker stop churchtools-api 2>/dev/null || true
    docker rm churchtools-api 2>/dev/null || true
fi

# Build the Docker image with verbose output
echo "Baue Docker-Image..."
docker build -t schowave/churchtools . || { echo "❌ Docker-Build fehlgeschlagen!"; exit 1; }
echo "✅ Docker-Image erfolgreich gebaut."

# Da die Anwendung nur im interaktiven Modus funktioniert, starten wir sie im Vordergrund
echo "Starte Docker-Container im Vordergrund..."
echo "Die Anwendung wird jetzt gestartet. Drücken Sie Ctrl+C, um sie zu beenden."
echo "Die Anwendung sollte unter http://localhost:5005 erreichbar sein."
echo ""

# Run the Docker container in foreground mode with TTY
docker run --rm -it -p 5005:5005 -v $(pwd)/data:/app/data --name churchtools-api schowave/churchtools python3 run_fastapi.py
