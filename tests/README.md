# ChurchTools API Tests

Diese Datei enthält Informationen zur Ausführung der Unit-Tests für die ChurchTools API-Anwendung.

## Teststruktur

Die Tests sind in folgende Kategorien unterteilt:

1. **Utils Tests** (`test_utils.py`): Tests für die Hilfsfunktionen wie Datumsverarbeitung und Textformatierung.
2. **Database Tests** (`test_database.py`): Tests für die Datenbankoperationen.
3. **Auth Tests** (`test_auth.py`): Tests für die Authentifizierungsfunktionen.
4. **Appointments Tests** (`test_appointments.py`): Tests für die Terminverwaltungsfunktionen.
5. **PDF Generator Tests** (`test_pdf_generator.py`): Tests für den PDF-Generator.

Zusätzlich gibt es eine Test-Suite (`test_suite.py`), die alle Tests zusammenfasst.

## Voraussetzungen

Um die Tests auszuführen, benötigen Sie:

1. Python 3.7 oder höher
2. Die in `requirements.txt` aufgeführten Abhängigkeiten
3. pytest und pytest-asyncio (bereits in requirements.txt enthalten)

## Tests ausführen

### Alle Tests ausführen

Um alle Tests auszuführen, verwenden Sie:

```bash
python -m pytest tests/
```

### Einzelne Testdateien ausführen

Um eine bestimmte Testdatei auszuführen, verwenden Sie:

```bash
python -m pytest tests/test_utils.py
```

### Test-Suite ausführen

Um die Test-Suite auszuführen, verwenden Sie:

```bash
python tests/test_suite.py
```

Hinweis: Die Test-Suite verwendet pytest, um alle Tests auszuführen, einschließlich der asynchronen Tests.

### Tests mit Berichterstattung ausführen

Um Tests mit Berichterstattung zur Codeabdeckung auszuführen, installieren Sie zuerst `pytest-cov`:

```bash
pip install pytest-cov
```

Dann führen Sie die Tests mit Abdeckungsbericht aus:

```bash
python -m pytest --cov=app tests/
```

Um einen HTML-Bericht zu generieren:

```bash
python -m pytest --cov=app --cov-report=html tests/
```

Der HTML-Bericht wird im Verzeichnis `htmlcov` erstellt.

## Hinweise

- Die Tests verwenden Mock-Objekte, um externe Abhängigkeiten wie die ChurchTools API zu simulieren.
- Für die Datenbanktests wird eine temporäre SQLite-Datenbank erstellt.
- Einige Tests erfordern möglicherweise Anpassungen an Ihre lokale Umgebung.
- Für asynchrone Tests wird pytest-asyncio verwendet, das die Ausführung von async/await-Funktionen in Tests ermöglicht.