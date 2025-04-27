#!/bin/bash

echo "=== ChurchTools API Docker Debug Script ==="
echo ""

# Überprüfen, ob der Container läuft
echo "Überprüfe laufende Container..."
CONTAINER_ID=$(docker ps -q --filter "name=churchtools-api")

if [ -z "$CONTAINER_ID" ]; then
    echo "❌ Kein laufender Container mit dem Namen 'churchtools-api' gefunden."
    
    # Überprüfen, ob der Container existiert, aber gestoppt ist
    STOPPED_CONTAINER=$(docker ps -a -q --filter "name=churchtools-api")
    if [ -n "$STOPPED_CONTAINER" ]; then
        echo "ℹ️ Container existiert, ist aber gestoppt. Logs anzeigen:"
        docker logs churchtools-api
        
        echo ""
        echo "Möchten Sie den Container neu starten? (j/n)"
        read -r RESTART
        if [ "$RESTART" = "j" ]; then
            docker start churchtools-api
            echo "Container wurde gestartet. Bitte warten Sie einen Moment und versuchen Sie dann, auf http://localhost:5005 zuzugreifen."
        fi
    else
        echo "ℹ️ Container existiert nicht. Bitte führen Sie zuerst 'run.sh' aus."
    fi
    
    exit 1
fi

echo "✅ Container läuft mit ID: $CONTAINER_ID"
echo ""

# Container-Logs anzeigen
echo "Container-Logs:"
docker logs churchtools-api
echo ""

# Netzwerk-Konfiguration überprüfen
echo "Netzwerk-Konfiguration im Container:"
docker exec churchtools-api sh -c "netstat -tulpn 2>/dev/null || ss -tulpn"
echo ""

# Überprüfen, ob der Port gebunden ist
echo "Port-Binding auf dem Host:"
if command -v ss &> /dev/null; then
    ss -tulpn | grep 5005
elif command -v netstat &> /dev/null; then
    netstat -tulpn | grep 5005
else
    echo "Weder 'ss' noch 'netstat' sind verfügbar."
fi
echo ""

# Überprüfen, ob der Port erreichbar ist
echo "Port-Erreichbarkeit testen:"
if command -v curl &> /dev/null; then
    curl -s -o /dev/null -w "HTTP-Status: %{http_code}\n" http://localhost:5005 || echo "❌ Verbindung fehlgeschlagen"
else
    echo "curl ist nicht verfügbar. Bitte installieren Sie curl oder testen Sie manuell mit einem Browser."
fi
echo ""

# Überprüfen, ob die Anwendung im Container läuft
echo "Prozesse im Container:"
docker exec churchtools-api ps aux
echo ""

echo "=== Debug abgeschlossen ==="
echo ""
echo "Wenn Sie immer noch Probleme haben, versuchen Sie Folgendes:"
echo "1. Container stoppen und entfernen: docker stop churchtools-api && docker rm churchtools-api"
echo "2. Image neu bauen: docker build -t schowave/churchtools ."
echo "3. Container mit explizitem Host-Binding starten:"
echo "   docker run -p 0.0.0.0:5005:5005 -v $(pwd)/data:/app/data --name churchtools-api schowave/churchtools"
echo ""
echo "Wenn das Problem weiterhin besteht, überprüfen Sie Ihre Firewall-Einstellungen und stellen Sie sicher,"
echo "dass Port 5005 nicht von einer anderen Anwendung verwendet wird."