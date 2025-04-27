#!/bin/bash

echo "=== ChurchTools API Docker Cleanup Script ==="
echo ""

# Überprüfen, ob der Container läuft
echo "Überprüfe laufende Container..."
CONTAINER_ID=$(docker ps -q --filter "name=churchtools-api")

if [ -n "$CONTAINER_ID" ]; then
    echo "Container mit ID $CONTAINER_ID gefunden. Stoppe den Container..."
    docker stop churchtools-api
    echo "Container gestoppt."
else
    echo "Kein laufender Container mit dem Namen 'churchtools-api' gefunden."
fi

# Überprüfen, ob der Container existiert
CONTAINER_EXISTS=$(docker ps -a -q --filter "name=churchtools-api")
if [ -n "$CONTAINER_EXISTS" ]; then
    echo "Entferne Container..."
    docker rm churchtools-api
    echo "Container entfernt."
else
    echo "Kein Container mit dem Namen 'churchtools-api' gefunden."
fi

echo ""
echo "Möchten Sie auch das Docker-Image entfernen? (j/n)"
read -r REMOVE_IMAGE
if [ "$REMOVE_IMAGE" = "j" ]; then
    echo "Entferne Docker-Image..."
    docker rmi schowave/churchtools
    echo "Docker-Image entfernt."
fi

echo ""
echo "=== Cleanup abgeschlossen ==="
echo ""
echo "Um die Anwendung neu zu starten, führen Sie 'run.sh' aus."