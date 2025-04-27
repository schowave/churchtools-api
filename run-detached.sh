#!/bin/bash

set -e  # Exit on error

echo "=== ChurchTools API Docker Setup (Detached Mode) ==="
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

# Erstelle ein angepasstes Dockerfile für den detached Modus
echo "Erstelle angepasstes Dockerfile für den detached Modus..."
cat > Dockerfile.detached << EOF
FROM schowave/churchtools

# Starte die Anwendung mit einem Shell-Skript, das ein TTY simuliert
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'cd /app && python3 run_fastapi.py' >> /app/start.sh && \
    chmod +x /app/start.sh

# Verwende das Shell-Skript als Entrypoint
ENTRYPOINT ["/app/start.sh"]
EOF

# Baue das angepasste Image
echo "Baue angepasstes Docker-Image..."
docker build -t schowave/churchtools:detached -f Dockerfile.detached . || { echo "❌ Docker-Build fehlgeschlagen!"; exit 1; }
echo "✅ Angepasstes Docker-Image erfolgreich gebaut."

# Run the Docker container in detached mode
echo "Starte Docker-Container im Hintergrund..."
docker run -d -p 5005:5005 -v $(pwd)/data:/app/data --name churchtools-api schowave/churchtools:detached || { echo "❌ Docker-Container konnte nicht gestartet werden!"; exit 1; }
echo "✅ Docker-Container im Hintergrund gestartet."

# Check if container is running
sleep 2
if docker ps | grep -q churchtools-api; then
    echo "✅ Container läuft."
    echo "Zeige Container-Logs:"
    docker logs churchtools-api
    echo ""
    echo "Die Anwendung sollte jetzt unter http://localhost:5005 erreichbar sein."
    echo "Um die Logs anzuzeigen, führen Sie './docker-logs.sh' aus."
else
    echo "❌ Container wurde gestartet, läuft aber nicht mehr."
    echo "Logs des fehlgeschlagenen Containers:"
    docker logs churchtools-api
    exit 1
fi

# Lösche das temporäre Dockerfile
rm Dockerfile.detached