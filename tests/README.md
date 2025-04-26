# ChurchTools API Tests

Dieses Verzeichnis enthält Unit-Tests für die ChurchTools API-Anwendung.

## Testausführung

### Lokale Ausführung

#### Für Linux/Windows:

Um die Tests lokal auszuführen, verwenden Sie den folgenden Befehl:

```bash
# Installiere die Abhängigkeiten
pip install -r requirements.txt

# Führe die Tests aus
python -m pytest tests/
```

#### Für macOS:

macOS-Benutzer können auf Probleme mit der reportlab-Installation stoßen. Hier sind drei Lösungsansätze:

**Option 1: Verwende das Installationsskript (empfohlen)**

```bash
# Mache das Skript ausführbar
chmod +x install-macos.sh

# Führe das Installationsskript aus
./install-macos.sh

# Aktiviere die virtuelle Umgebung (falls noch nicht aktiviert)
source venv/bin/activate

# Führe die Tests aus
python -m pytest tests/
```

**Option 2: Manuelle Installation**

```bash
# Erstelle eine virtuelle Umgebung
python -m venv venv
source venv/bin/activate

# Installiere reportlab ohne C-Erweiterungen
pip install --no-binary=reportlab reportlab==3.5.68

# Installiere die restlichen Abhängigkeiten
pip install -r requirements-macos.txt

# Führe die Tests aus
python -m pytest tests/
```

**Option 3: Verwende Docker**

```bash
# Baue das Docker-Image
docker build -t churchtools-api:test .

# Führe die Tests im Container aus
docker run --rm churchtools-api:test python -m pytest tests/
```

### Ausführung mit Codeabdeckungsbericht

Um die Tests mit einem Codeabdeckungsbericht auszuführen:

```bash
python -m pytest --cov=app tests/ --cov-report=term
```

Für einen HTML-Bericht:

```bash
python -m pytest --cov=app tests/ --cov-report=html
```

### IntelliJ Run-Konfigurationen

Es wurden zwei IntelliJ Run-Konfigurationen erstellt:

1. **Run Tests with Coverage**: Führt alle Tests aus und zeigt einen Codeabdeckungsbericht im Terminal an
2. **Run Tests with HTML Coverage**: Führt alle Tests aus und generiert einen HTML-Codeabdeckungsbericht

## Teststruktur

Die Tests sind in folgende Kategorien unterteilt:

1. **Utils Tests**: Testen Hilfsfunktionen mit 97% Codeabdeckung
2. **Database Tests**: Testen Datenbankoperationen mit 84% Codeabdeckung
3. **Auth Tests**: Testen Authentifizierungsfunktionen mit 43% Codeabdeckung
4. **Appointments Tests**: Testen Terminverwaltungsfunktionen mit 23% Codeabdeckung
5. **PDF Generator Tests**: Testen PDF-Erstellungsfunktionen mit 82% Codeabdeckung

Die Gesamtcodeabdeckung beträgt 51%.

## CI/CD-Pipeline

Die Tests werden automatisch in der GitHub Actions-Pipeline ausgeführt. Es gibt zwei Workflows:

1. **test-and-build.yml**: Wird bei jedem Push und Pull Request ausgeführt
   - Führt alle Tests mit Codeabdeckungsbericht aus
   - Lädt den Codeabdeckungsbericht zu Codecov hoch
   - Baut das Docker-Image (ohne Push)

2. **release.yml**: Wird nur manuell über den GitHub Actions UI ausgeführt
   - Erfordert die Eingabe einer Version (z.B. v1.0.0)
   - Führt alle Tests mit Codeabdeckungsbericht aus
   - Lädt den Codeabdeckungsbericht zu Codecov hoch
   - Baut das Docker-Image und pusht es zur GitHub Container Registry (GHCR)
   - Taggt das Image mit der angegebenen Version und "latest"