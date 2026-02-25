# Refactoring-Plan: Phase 3 — Architektur, Sicherheit, Frontend, Infrastruktur

## Kontext
Phase 1 (toter Code, Duplikate, Magic Numbers) und Phase 2 (Konsistenz, DRY, Strukturverbesserungen) sind abgeschlossen. Dieser Plan enthält die verbleibenden Refactoring-Möglichkeiten, nach Priorität geordnet.

---

## Priorität 1: Sicherheit & Robustheit

### 1.1 Path-Traversal in `/download/{filename}` absichern
**Datei:** `app/api/appointments.py:392-397`
**Problem:** Der Endpunkt akzeptiert beliebige Dateinamen ohne Validierung. Ein Angreifer könnte `../../etc/passwd` oder ähnliches als `filename` senden.
**Aktion:**
```python
@router.get("/download/{filename}")
async def download_file(filename: str):
    # Nur den Dateinamen ohne Pfad-Komponenten zulassen
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(Config.FILE_DIRECTORY, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=safe_filename)
```

### 1.2 Secret Key aus Konfiguration entfernen
**Datei:** `app/config.py:25`
**Problem:** `SECRET_KEY` enthält einen hart-codierten Fallback-Wert mit dem CHURCHTOOLS_BASE als Bestandteil. Der Key ist vorhersagbar wenn kein `FLASK_SECRET_KEY` gesetzt ist.
**Aktion:** Entweder Pflicht-Umgebungsvariable machen (Exception bei fehlendem Wert) oder einen sicheren Zufallswert generieren. Prüfen ob `SECRET_KEY` überhaupt noch gebraucht wird (FastAPI nutzt es nicht direkt — es scheint ein Überbleibsel aus Flask-Zeiten zu sein).

### 1.3 Cookie-Sicherheit verbessern
**Datei:** `app/api/auth.py:35`
**Problem:** `set_cookie(key=..., value=login_token)` setzt kein `httponly`, `secure`, oder `samesite`-Flag.
**Aktion:**
```python
redirect.set_cookie(
    key=Config.COOKIE_LOGIN_TOKEN,
    value=login_token,
    httponly=True,
    samesite="lax",
    secure=True,  # nur wenn HTTPS
)
```

### 1.4 Fehlende Error-Behandlung bei API-Responses
**Datei:** `app/api/appointments.py:55-58`
**Problem:** `fetch_appointments()` greift direkt auf `response.json()['data']` zu, ohne den Statuscode zu prüfen (nur `status_code == 200` gecheckt, aber kein else-Zweig → stille Fehler, fehlende Appointments).
**Aktion:** Logging oder Exception für Nicht-200-Responses bei einzelnen Calendar-Requests hinzufügen.

---

## Priorität 2: Architektur & Codequalität

### 2.1 `database.py` aufteilen: Models vs. CRUD vs. Session
**Datei:** `app/database.py` (119 Zeilen)
**Problem:** Enthält Models (Appointment, ColorSetting), Session-Setup, Schema-Erstellung UND alle CRUD-Operationen in einer Datei. Das `app/models/` Verzeichnis existiert bereits, ist aber leer.
**Aktion:**
- `app/models/appointment.py` — Appointment-Model
- `app/models/color_setting.py` — ColorSetting-Model
- `app/database.py` — Engine, Session, Base, `get_db()`, `create_schema()`
- `app/crud.py` oder innerhalb der bestehenden Dateien — CRUD-Funktionen

### 2.2 `appointments.py` aufteilen (398 Zeilen — größte Datei)
**Datei:** `app/api/appointments.py`
**Problem:** Enthält API-Helper (`fetch_calendars`, `fetch_appointments`), Daten-Transformation (`appointment_to_dict`), Business-Logik (`_prepare_selected_appointments`, `handle_jpeg_generation`) und Route-Handler in einer Datei.
**Mögliche Aufteilung:**
- `app/services/churchtools_client.py` — `fetch_calendars()`, `fetch_appointments()`, `_auth_headers()`
- `app/services/jpeg_generator.py` — `handle_jpeg_generation()`
- `app/api/appointments.py` — Route-Handler und Template-Logik

### 2.3 Dicts durch Dataclasses/Pydantic-Models ersetzen
**Problem:** Appointments und ColorSettings werden durchgängig als untypisierte Dicts weitergereicht. Typos in Dict-Keys (`color_settings['backgorund_color']`) werden erst zur Laufzeit entdeckt.
**Betroffene Stellen:**
- `appointment_to_dict()` gibt ein Dict zurück → `AppointmentView`-Dataclass
- `load_color_settings()` / `save_color_settings()` → `ColorSettings`-Pydantic-Model
- `_build_template_context()` nimmt `dict` als color_settings → typisierter Parameter
**Aktion:** Schrittweise Migration, starting mit `ColorSettings` da es überall durchgereicht wird.

### 2.4 Hardcoded `"default"` als Color-Setting-Name
**Dateien:** `app/api/appointments.py:226,247,252,358`
**Problem:** Der String `"default"` wird 4x wiederholt als Setting-Name.
**Aktion:** Konstante `DEFAULT_SETTING_NAME = "default"` in Config oder database.py.

### 2.5 Doppelter Startup-Code: `run_fastapi.py` vs. `app/main.py:41-43`
**Problem:** Beide Dateien enthalten `uvicorn.run()` mit identischen Parametern. `run_fastapi.py` ist der Docker-Entrypoint, `app/main.py` hat den gleichen Code als `if __name__ == "__main__"`.
**Aktion:** `if __name__`-Block in `main.py` entfernen (Docker nutzt `run_fastapi.py`, lokale Entwicklung nutzt `run.sh` → `run_fastapi.py`).

### 2.6 Doppelter `Path(FILE_DIRECTORY).mkdir()` Aufruf
**Dateien:** `app/config.py:30` und `app/main.py:23`
**Problem:** Beide erstellen dasselbe Verzeichnis.
**Aktion:** Nur an einer Stelle behalten (Config oder main, nicht beides).

### 2.7 Unused import `Depends` und `HTTPException` in `main.py`
**Datei:** `app/main.py:1`
**Problem:** `Depends` und `HTTPException` werden importiert aber nicht verwendet.
**Aktion:** Entfernen.

---

## Priorität 3: Frontend & Templates

### 3.1 Inline-JavaScript aus `appointments.html` in externe Datei extrahieren
**Datei:** `app/templates/appointments.html` (526 Zeilen, davon ~220 Zeilen JavaScript)
**Problem:** 7 separate `<script>`-Blöcke im `<head>` und `<body>`, davon enthalten viele DOM-Manipulation die erst nach DOMContentLoaded laufen sollte. Ein Block (Zeile 192-197, `alphaSlider`) referenziert DOM-Elemente im `<head>` bevor sie existieren.
**Aktion:**
- JavaScript in `app/static/js/appointments.js` extrahieren
- Template-Variablen über `data-`Attribute oder ein `<script type="application/json">` Block übergeben
- Die leere Datei `app/static/js/datepicker.js` enthält keine Logik — Datepicker-Code lebt inline in der HTML → dorthin verschieben oder Datei löschen

### 3.2 `alphaSlider`-Script führt zu Runtime-Error
**Datei:** `app/templates/appointments.html:192-197`
**Problem:** Dieses Script steht im `<head>` und sucht `document.getElementById('alpha')` — das Element existiert aber erst im `<body>`. Ergebnis: `alphaSlider` ist `null`, `addEventListener` wirft einen Error.
**Aktion:** Script nach dem Element platzieren oder in ein `DOMContentLoaded`-Event wrappen. Wird durch 3.1 automatisch gelöst.

### 3.3 Duplicate `$(document).ready()` Verschachtelung
**Datei:** `app/templates/appointments.html:149+174`
**Problem:** Ein `$(document).ready()` ist innerhalb eines anderen `$(document).ready()` verschachtelt. Funktioniert, ist aber unnötig.
**Aktion:** Zusammenführen in ein einzelnes Ready-Event.

### 3.4 CSS-Deduplizierung: Massive Safari-Overrides
**Dateien:** `common.css`, `appointments.css`, `login.css`, `overview.css`
**Problem:** Jede CSS-Datei hat einen großen `@supports (-webkit-touch-callout: none)` Block der fast identische Styles für Safari wiederholt. Viele davon sind redundant weil `common.css` bereits die Basis-Styles setzt.
**Aktion:** Safari-Overrides in eine zentrale Datei konsolidieren (z.B. `common.css` oder ein neues `safari-fixes.css`), seitenspezifische Overrides minimal halten.

### 3.5 Leere `datepicker.js` Datei
**Datei:** `app/static/js/datepicker.js` (0 Zeilen)
**Problem:** Datei existiert, wird aber nirgends referenziert und enthält keinen Code.
**Aktion:** Löschen, oder Datepicker-Logic aus dem HTML dorthin verschieben (siehe 3.1).

### 3.6 `prefixed.css` und `cross-browser.css` — IE/Edge Legacy-Code
**Dateien:** `app/static/css/prefixed.css`, `app/static/css/cross-browser.css`
**Problem:** Enthalten umfangreiche Fixes für Internet Explorer (IE 11, Edge Legacy) die in 2026 nicht mehr relevant sind. Viele der Utility-Klassen (`.flex`, `.transform-rotate`, `.ie-fix`, `.edge-fix`) werden im Projekt nicht verwendet.
**Aktion:**
- Prüfen welche Klassen tatsächlich in den Templates genutzt werden (vermutlich keine)
- Nicht genutzte Klassen entfernen
- IE-spezifische `@media`-Blöcke entfernen
- Dateien möglicherweise ganz entfernen wenn nur moderne Browser unterstützt werden sollen

---

## Priorität 4: Tests

### 4.1 Fehlende Tests für Handler-Funktionen
**Problem:** Die Handler `_handle_fetch_appointments`, `_handle_generate_pdf`, `_handle_generate_jpeg` und `_prepare_selected_appointments` haben keine direkten Tests. Nur die Route-Funktionen (`appointments_page`, `process_appointments`) werden getestet, aber `process_appointments` hat keinen Test.
**Aktion:** Tests für `process_appointments` mit verschiedenen Button-Szenarien (fetch, pdf, jpeg) hinzufügen.

### 4.2 Kein Test für `create_schema()`
**Problem:** `database.py:create_schema()` wird nie getestet.
**Aktion:** Einfacher Test der prüft dass Tabellen angelegt werden.

### 4.3 `test_suite.py` und `conftest.py` duplizieren `sys.path` Setup
**Dateien:** `tests/test_suite.py:6`, `tests/conftest.py:6`
**Problem:** Beide fügen den Parent-Pfad zu `sys.path` hinzu. `conftest.py` wird von pytest automatisch geladen, `test_suite.py` ist ein manueller Runner.
**Aktion:** `test_suite.py` ist redundant wenn pytest direkt genutzt wird → Löschen oder als Alternative dokumentieren.

### 4.4 `conftest.py` — unnötiger `pytest_addoption`
**Datei:** `tests/conftest.py:15-17`
**Problem:** Setzt `asyncio_default_fixture_loop_scope` was bereits in `pytest.ini` konfiguriert werden könnte.
**Aktion:** In `pytest.ini` verschieben:
```ini
[pytest]
asyncio_mode = strict
asyncio_default_fixture_loop_scope = function
```

---

## Priorität 5: Infrastruktur & Dependencies

### 5.1 Python 3.10 im Dockerfile — Upgrade auf 3.12+
**Datei:** `Dockerfile:2,25`
**Problem:** Python 3.10 ist End-of-Life im Oktober 2026. Dependencies (FastAPI, SQLAlchemy) unterstützen längst 3.12.
**Aktion:** `python:3.12-slim` als Base-Image verwenden.

### 5.2 Veraltete Dependencies
**Datei:** `requirements-base.txt`
**Stark veraltet (2+ Jahre):**
- `fastapi==0.95.1` → aktuell 0.115+ (Pydantic v2 Support, Performance)
- `uvicorn==0.22.0` → aktuell 0.34+
- `sqlalchemy==2.0.12` → aktuell 2.0.36+
- `pydantic==1.10.7` → **Pydantic v2** (Major Breaking Change, aber FastAPI unterstützt es)
- `httpx==0.24.0` → aktuell 0.28+
- `jinja2==3.1.2` → aktuell 3.1.5+ (Security Fixes)
- `python-multipart==0.0.6` → aktuell 0.0.20+ (Security Fixes)
**Aktion:** Schrittweises Upgrade, Test-Suite als Safety Net nutzen.

### 5.3 Drei separate Requirements-Dateien
**Dateien:** `requirements.txt`, `requirements-base.txt`, `requirements-macos.txt`
**Problem:** `requirements-macos.txt` ist fast identisch mit `requirements-base.txt` plus `pypdf`. Die Aufteilung zwischen `requirements.txt` und `requirements-base.txt` ist unklar (nur `reportlab` Unterschied).
**Aktion:** Konsolidieren zu `requirements.txt` (prod) und optional `requirements-dev.txt` (test dependencies).

### 5.4 `install-macos.sh` — veraltetes Installationsscript
**Datei:** `install-macos.sh`
**Problem:** Versucht `reportlab==3.5.68` mit `--global-option` zu installieren — das ist veraltet und funktioniert mit modernem pip nicht mehr.
**Aktion:** Aktualisieren oder entfernen wenn nicht mehr benötigt.

### 5.5 GitHub Actions — veraltete Action-Versionen
**Datei:** `.github/workflows/test-and-build.yml`
**Problem:** Verwendet `actions/checkout@v3` (aktuell v4), `docker/setup-buildx-action@v2` (aktuell v3), `docker/build-push-action@v4` (aktuell v5), `codecov/codecov-action@v3` (aktuell v5).
**Aktion:** Auf aktuelle Versionen upgraden.

### 5.6 `pytest-cov` als Dev-Dependency fehlt
**Datei:** `requirements-base.txt`
**Problem:** GitHub Actions installiert `pytest-cov` manuell im CI-Step, aber es fehlt in den Requirements.
**Aktion:** `pytest-cov` in Requirements aufnehmen.

---

## Priorität 6: Kleinigkeiten / Nice-to-have

### 6.1 German/English Mix in Code-Kommentaren
**Problem:** Kommentare sind teils Deutsch (`# Lade Farbeinstellungen`, `# Leere Initialisierungsdatei`), teils Englisch. Funktionsnamen und Variablen sind Englisch, UI-Texte sind Deutsch.
**Aktion:** Kommentare auf Englisch vereinheitlichen (Code-Sprache = Englisch, UI = Deutsch).

### 6.2 `__init__.py` Dateien enthalten deutschen Kommentar
**Dateien:** `app/api/__init__.py`, `app/models/__init__.py`, `app/services/__init__.py`
**Problem:** Alle drei enthalten `# Leere Initialisierungsdatei` — überflüssig.
**Aktion:** Dateien leer machen oder Kommentar entfernen.

### 6.3 `normalize.css` — Source-Angabe fehlt
**Datei:** `app/static/css/normalize.css` (nicht gelesen, aber referenziert)
**Problem:** Sollte eine bekannte normalize.css Version sein — prüfen ob es die offizielle Version ist und ob sie aktuell ist.

### 6.4 Doppelte `var` Deklaration in JavaScript
**Datei:** `app/templates/appointments.html:23+79`
**Problem:** `var initialStartDate` wird zweimal deklariert (Zeile 23 und 79). Die zweite überschreibt die erste.
**Aktion:** Erste Deklaration entfernen (der Wert wird erst nach Zeile 76 korrekt sein).

---

## Empfohlene Reihenfolge

1. **Priorität 1** (Sicherheit) — sofort umsetzen, geringes Risiko
2. **Priorität 2.5-2.7** (Quick Wins) — schnell erledigt, kein Risiko
3. **Priorität 3.2** (alphaSlider Bug) — echter Bug, Fix ist trivial
4. **Priorität 2.1-2.3** (Architektur) — größerer Umbau, aber höchster langfristiger Nutzen
5. **Priorität 4** (Tests) — vor oder parallel zu Architektur-Änderungen
6. **Priorität 5** (Infrastruktur) — separat planbar
7. **Priorität 3+6** (Frontend, Kleinigkeiten) — bei Gelegenheit

## Dateien die betroffen wären

| Datei | Prioritäten |
|-------|-------------|
| `app/api/appointments.py` | 1.1, 1.4, 2.2, 2.3, 2.4 |
| `app/api/auth.py` | 1.3 |
| `app/config.py` | 1.2, 2.4, 2.6 |
| `app/database.py` | 2.1, 2.3 |
| `app/main.py` | 2.5, 2.6, 2.7 |
| `app/models/__init__.py` | 2.1, 6.2 |
| `app/templates/appointments.html` | 3.1, 3.2, 3.3, 6.4 |
| `app/static/css/*.css` | 3.4, 3.6 |
| `app/static/js/datepicker.js` | 3.5 |
| `tests/` | 4.1–4.4 |
| `Dockerfile` | 5.1 |
| `requirements*.txt` | 5.2, 5.3 |
| `.github/workflows/test-and-build.yml` | 5.5, 5.6 |
| `install-macos.sh` | 5.4 |
