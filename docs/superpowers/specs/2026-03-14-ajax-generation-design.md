# Design: AJAX-basierte PDF/JPEG-Generierung

## Problem

Beim deployten Betrieb (Cloudflare Tunnel → Docker auf Synology NAS) funktioniert der native HTML Form-POST nicht korrekt:

1. **Termin-Selektion ignoriert:** Abgewählte Termine erscheinen trotzdem im generierten PDF/JPEG
2. **Transparenz ignoriert:** Alpha-Wert wird nicht korrekt übertragen, immer volle Transparenz

Lokal funktioniert beides einwandfrei. Das AJAX-basierte Termine-Abholen funktioniert auch deployed korrekt.

## Lösung

Die PDF/JPEG-Generierung von nativem Form-Submit auf AJAX umstellen. Gleicher Pattern wie das bestehende `fetchAppointmentsAjax()`.

## Änderungen

### 1. Neuer JSON-API-Endpoint (Backend)

**Datei:** `app/api/appointments.py`

Neuer Endpoint `POST /api/generate` der JSON empfängt:

```json
{
  "type": "pdf",
  "start_date": "2026-03-14",
  "end_date": "2026-03-21",
  "calendar_ids": ["1", "2", "3"],
  "appointment_ids": ["123", "456"],
  "color_settings": {
    "background_color": "#ffffff",
    "background_alpha": 128,
    "date_color": "#c1540c",
    "description_color": "#4e4e4e"
  },
  "additional_infos": {
    "123": "Zusätzlicher Text",
    "456": ""
  }
}
```

- `type`: `"pdf"` oder `"jpeg"`
- `calendar_ids`: Strings (wie im bestehenden Code), werden intern zu int konvertiert
- `appointment_ids`: Muss mindestens einen Eintrag enthalten

**Erfolgs-Response:** `{"download_url": "/download/2026-03-14_Termine.pdf"}`

**Fehler-Responses:**
- `401 {"error": "not_authenticated"}` — kein Login-Token oder abgelaufen
- `400 {"error": "no_appointments_selected"}` — leere `appointment_ids`-Liste
- `400 {"error": "invalid_type"}` — `type` ist weder "pdf" noch "jpeg"

**Backend-Logik:**
- Neue Funktion `_prepare_selected_appointments_from_json()` die `additional_infos` als Dict statt aus `request.form()` liest. Ersetzt die Form-Data-Abhängigkeit der bestehenden Funktion.
- `additional_infos` werden weiterhin via `save_additional_infos()` in die DB persistiert (wie bisher).
- `color_settings` werden via `save_color_settings()` in die DB persistiert (wie bisher).
- Auth: Login-Token aus Cookie lesen, `AuthenticationError` → 401 Response mit `window.location.href = '/'` im Frontend.

### 2. JS-Submit statt Form-Submit (Frontend)

**Datei:** `app/static/js/appointments.js`

Neue Funktion `generateOutput(type)`:
1. Sammelt ausgewählte `appointment_ids` aus `.appointment-checkbox:checked`
2. Falls keine ausgewählt: Fehlermeldung anzeigen, abbrechen
3. Sammelt `additional_infos` aus den Textareas (`name="additional_info_{id}"`)
4. Liest Farb- und Alpha-Werte aus den Input-Feldern
5. Liest `start_date`, `end_date` aus Hidden-Fields und `calendar_ids` aus checked Calendar-Checkboxen
6. Sendet JSON per `fetch('POST', '/api/generate')` mit `Content-Type: application/json`
7. Bei 401: `window.location.href = '/'`
8. Bei Erfolg: `window.location.href = data.download_url` für Download
9. Bei Fehler: Fehlermeldung anzeigen

**Spinner-Handling:** `monitorDownload()` wird nicht mehr verwendet. Stattdessen:
- Spinner anzeigen vor `fetch()`
- Spinner ausblenden im `.then()` / `.catch()` Block
- `monitorDownload()` Funktion kann entfernt werden

### 3. Template anpassen

**Datei:** `app/templates/appointments.html`

- `<form method="POST">` bleibt als `<form>` (ohne `method`/`action`) erhalten, da die Inputs weiterhin per `id` gelesen werden und das Form-Element keine Funktionalität mehr hat. Alternativ zu `<div>` ändern — kein funktionaler Unterschied.
- Generate-Buttons: `type="submit"` → `type="button"`
- `name="generate_pdf"` und `name="generate_jpeg"` Attribute entfernen
- Click-Handler per JS (nicht inline `onclick`), konsistent mit bestehendem Code-Stil

### 4. Alten POST-Endpoint entfernen

**Datei:** `app/api/appointments.py`

- `process_appointments()` (`POST /appointments`) komplett entfernen
- `_handle_generate_pdf()` und `_handle_generate_jpeg()` entfernen
- `_prepare_selected_appointments()` durch die neue JSON-Variante ersetzen

Der alte Endpoint wird von nichts anderem aufgerufen und ist nach der Umstellung toter Code.

## Nicht im Scope

- Appointment-ID-Eindeutigkeit (separates Issue, nicht Ursache des deployed-Bugs)
- Transparenz-Slider Semantik (Label "Transparenz" vs. tatsächliche Opacity-Steuerung)
- Cloudflare-Tunnel-Konfiguration

## Risiken

- **Download-Trigger:** `window.location.href = download_url` triggert den Download, da der Server `FileResponse` mit passendem Content-Type zurückgibt. Falls der Browser den Download nicht startet, kann alternativ ein temporärer `<a download>` Link erstellt und geklickt werden.
