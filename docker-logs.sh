#!/bin/bash

echo "=== ChurchTools API Docker Logs ==="
echo ""

# Überprüfen, ob der Container existiert
CONTAINER_EXISTS=$(docker ps -a -q --filter "name=churchtools-api")
if [ -z "$CONTAINER_EXISTS" ]; then
    echo "❌ Kein Container mit dem Namen 'churchtools-api' gefunden."
    echo "Bitte führen Sie zuerst 'run.sh' aus, um den Container zu starten."
    exit 1
fi

# Logs anzeigen
echo "Logs des Containers 'churchtools-api':"
echo "-------------------------------------"
docker logs churchtools-api
echo "-------------------------------------"

# Container-Status anzeigen
echo ""
echo "Container-Status:"
docker ps -a --filter "name=churchtools-api" --format "Status: {{.Status}}"
echo ""

# Prüfen, ob der Container läuft
if docker ps -q --filter "name=churchtools-api" | grep -q .; then
    echo "✅ Container läuft."
else
    echo "❌ Container ist gestoppt oder hat einen Fehler."
    
    # Prüfen, ob der Container mit einem Fehler beendet wurde
    EXIT_CODE=$(docker inspect --format='{{.State.ExitCode}}' churchtools-api)
    if [ "$EXIT_CODE" != "0" ]; then
        echo "Exit-Code: $EXIT_CODE"
        echo ""
        echo "Mögliche Fehlerursachen:"
        echo "- Python-Fehler in der Anwendung"
        echo "- Probleme mit den Umgebungsvariablen"
        echo "- Probleme mit dem Volume-Mounting"
        echo "- Fehlende Berechtigungen"
        echo ""
        echo "Versuchen Sie, den Container mit folgendem Befehl zu starten, um mehr Informationen zu erhalten:"
        echo "docker run --rm -it -p 5005:5005 -v $(pwd)/data:/app/data schowave/churchtools /bin/bash"
        echo "Dann führen Sie im Container aus: python3 run_fastapi.py"
    fi
fi