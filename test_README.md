# Unit-Tests für ChurchTools API

Diese Datei enthält Informationen zur Ausführung der Unit-Tests für die ChurchTools API-Anwendung.

## Voraussetzungen

Stellen Sie sicher, dass alle erforderlichen Abhängigkeiten installiert sind:

```bash
pip install -r requirements.txt
```

## Tests ausführen

Sie können die Tests mit dem folgenden Befehl ausführen:

```bash
python -m unittest test_app.py
```

Oder mit detaillierteren Ausgaben:

```bash
python -m unittest -v test_app.py
```

## Testabdeckung

Die Tests decken folgende Funktionalitäten ab:

1. **Login-Funktionalität**
   - Test, ob die Login-Seite geladen wird
   - Test für erfolgreichen Login
   - Test für fehlgeschlagenen Login
   - Test für Logout-Funktionalität

2. **Geschützte Routen**
   - Test, ob geschützte Routen zur Login-Seite umleiten, wenn nicht eingeloggt

3. **Terminverwaltung**
   - Test, ob die Terminseite mit Login geladen wird
   - Test für das Abrufen von Terminen
   - Test für die PDF-Generierung von Terminen
   - Test für die JPEG-Generierung von Terminen

## Mocking

Die Tests verwenden das `unittest.mock`-Modul, um externe Abhängigkeiten wie die ChurchTools-API zu simulieren. Dies ermöglicht das Testen der Anwendung ohne tatsächliche API-Aufrufe.

## Testdatenbank

Die Tests verwenden eine separate Testdatenbank (`test_database.db`), die nach jedem Test automatisch gelöscht wird, um Seiteneffekte zu vermeiden.

## Testdateien

Die Tests erstellen temporäre Dateien im Verzeichnis `test_files`, das nach jedem Test automatisch aufgeräumt wird.