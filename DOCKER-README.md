# ChurchTools API Docker-Anleitung

Diese Anleitung hilft Ihnen bei der Verwendung der ChurchTools API mit Docker.

## Voraussetzungen

- Docker installiert und laufend
- Bash-Shell (für Linux/macOS) oder Git Bash/WSL (für Windows)

## Schnellstart

1. Führen Sie das Skript `run.sh` aus, um das Docker-Image zu bauen und den Container zu starten:

```bash
./run.sh
```

Dieses Skript startet die Anwendung im Vordergrund. Sie können die Anwendung mit Ctrl+C beenden.

2. Alternativ können Sie die Anwendung im Hintergrund starten:

```bash
./run-detached.sh
```

3. Öffnen Sie einen Browser und navigieren Sie zu `http://localhost:5005`

## Fehlerbehebung bei Startproblemen

Wenn der Docker-Container nicht startet oder Sie eine "Connection refused"-Fehlermeldung erhalten, können Sie folgende Schritte zur Fehlerbehebung durchführen:

### 1. Container-Logs anzeigen

Führen Sie das Logs-Skript aus, um die Container-Logs anzuzeigen:

```bash
./docker-logs.sh
```

Das Skript zeigt Ihnen:
- Die Container-Logs
- Den Container-Status
- Mögliche Fehlerursachen, wenn der Container nicht läuft

### 2. Interaktiver Modus

Starten Sie den Container im interaktiven Modus, um die Anwendung manuell zu starten und Fehler direkt zu sehen:

```bash
./docker-interactive.sh
```

Im Container können Sie dann die Anwendung manuell starten:

```bash
python3 run_fastapi.py
```

### 3. Diagnose-Skript ausführen

Führen Sie das Diagnose-Skript aus, um den Status des Containers zu überprüfen:

```bash
./docker-debug.sh
```

Das Skript zeigt Ihnen:
- Ob der Container läuft
- Die Container-Logs
- Die Netzwerk-Konfiguration im Container
- Das Port-Binding auf dem Host
- Die Port-Erreichbarkeit
- Die laufenden Prozesse im Container

### 4. Container neu starten

Wenn der Container nicht richtig läuft, können Sie ihn mit dem Cleanup-Skript stoppen und entfernen:

```bash
./docker-cleanup.sh
```

Anschließend können Sie den Container mit `run.sh` neu starten.

### 5. Weitere Überprüfungen

- Stellen Sie sicher, dass Port 5005 nicht von einer anderen Anwendung verwendet wird
- Überprüfen Sie Ihre Firewall-Einstellungen
- Stellen Sie sicher, dass Docker die Berechtigung hat, auf das Netzwerk zuzugreifen
- Überprüfen Sie, ob die Datenbank-Datei im data-Verzeichnis existiert und Schreibrechte hat

## Übersicht der Skripte

| Skript | Beschreibung |
|--------|--------------|
| `run.sh` | Baut das Docker-Image und startet den Container im Vordergrund |
| `run-detached.sh` | Baut das Docker-Image und startet den Container im Hintergrund |
| `docker-logs.sh` | Zeigt die Container-Logs an |
| `docker-interactive.sh` | Startet den Container im interaktiven Modus |
| `docker-debug.sh` | Führt eine umfassende Diagnose durch |
| `docker-cleanup.sh` | Stoppt und entfernt den Container |

## Manuelles Bauen und Starten

Wenn Sie den Container manuell bauen und starten möchten:

```bash
# Image bauen
docker build -t schowave/churchtools .

# Container starten
docker run -d -p 5005:5005 -v $(pwd)/data:/app/data --name churchtools-api schowave/churchtools
```

## In den laufenden Container einsteigen

```bash
docker exec -it churchtools-api /bin/bash
```

## Datenbank-Verzeichnis

Die Datenbank wird im `data`-Verzeichnis gespeichert. Stellen Sie sicher, dass dieses Verzeichnis existiert und Schreibrechte hat:

```bash
mkdir -p ./data
chmod 777 ./data
```