#!/bin/bash

echo "=== ChurchTools API Docker Interactive Mode ==="
echo ""

# Überprüfen, ob der Container bereits existiert
CONTAINER_EXISTS=$(docker ps -a -q --filter "name=churchtools-api")
if [ -n "$CONTAINER_EXISTS" ]; then
    echo "Container existiert bereits. Stoppe und entferne ihn..."
    docker stop churchtools-api 2>/dev/null || true
    docker rm churchtools-api 2>/dev/null || true
fi

# Create data directory if it doesn't exist
echo "Erstelle data-Verzeichnis..."
mkdir -p ./data
chmod 777 ./data  # Ensure write permissions

echo "Starte Container im interaktiven Modus..."
echo "Sie werden in eine Bash-Shell im Container weitergeleitet."
echo "Dort können Sie die Anwendung manuell starten mit: python3 run_fastapi.py"
echo "Drücken Sie Ctrl+C, um die Anwendung zu beenden, und exit, um den Container zu verlassen."
echo ""

# Starte den Container im interaktiven Modus
docker run --rm -it \
    -p 5005:5005 \
    -v $(pwd)/data:/app/data \
    --name churchtools-api-interactive \
    schowave/churchtools \
    /bin/bash

echo ""
echo "Container wurde beendet."