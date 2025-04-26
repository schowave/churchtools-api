# ChurchTools API Tests

Dieses Verzeichnis enthält Unit-Tests für die ChurchTools API-Anwendung.

## Testausführung

### Lokale Ausführung

Um die Tests lokal auszuführen, verwenden Sie den folgenden Befehl:

```bash
python -m pytest tests/
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