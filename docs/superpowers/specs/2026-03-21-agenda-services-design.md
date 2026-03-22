# Agenda & Dienstplan — Design Spec

## Problem

Die App nutzt aktuell nur Kalender-Termine aus der ChurchTools API, um Ankündigungsfolien zu generieren. Für das Medienteam fehlen zwei häufig benötigte Ansichten: der Gottesdienst-Ablaufplan (Agenda) und die Dienstplan-Übersicht (wer macht was).

## Lösung

Zwei neue eigenständige Seiten in der bestehenden App, die weitere ChurchTools-API-Endpunkte nutzen.

## Datenmodell

### Neue ChurchTools-Client-Funktionen

**Events laden:**
- `fetch_events(login_token, from, to, calendar_ids, client)` → `GET /events?from=...&to=...&include=eventServices`
- Client-seitige Filterung nach ausgewählten Kalender-IDs über `calendar.domainIdentifier` (String) — muss gegen die übergebenen Kalender-IDs gematcht werden
- Pagination: Die Events-API nutzt `from`/`to` Range-Modus, in dem `page`/`limit` ignoriert werden. Kein manuelles Paginieren nötig. Hinweis: `to` ist aktuell inklusiv, wird aber in Zukunft exklusiv — deshalb `to` + 1 Tag setzen.
- Abgesagte Events (`isCanceled: true`) werden ausgefiltert
- Rückgabe pro Event: `id`, `name`, `startDate`, `endDate`, `calendar`, `eventServices[]`

**Agenda laden:**
- `fetch_agenda(login_token, event_id, client)` → `GET /events/{eventId}/agenda`
- Rückgabe: Liste von Agenda-Items mit `position`, `title`, `start` (ISO-Timestamp vom API), `duration` (Sekunden), `note`, `responsible.persons[]`, Song-Referenz, `isBeforeEvent`
- Bei 404 (Event hat keine Agenda): leere Liste zurückgeben, kein Fehler

### Pydantic-Modelle

```python
class EventService:
    service_id: int
    name: str               # z.B. "Predigt", "Worship-Leitung"
    person_name: str | None # None wenn Slot nicht besetzt
    is_accepted: bool       # Zugesagt?

class EventSummary:
    id: int
    name: str
    start_date: str
    end_date: str
    calendar_name: str
    services: list[EventService]

class AgendaItem:
    position: int
    type: str               # "default", "song", "header"
    title: str
    start: str | None       # ISO-Timestamp vom API (nicht manuell berechnet)
    duration_seconds: int   # In Sekunden (nicht Minuten), Anzeige als MM:SS
    note: str | None
    responsible_names: list[str]
    is_before_event: bool   # True = vor dem offiziellen Event-Start
    # Song-spezifische Felder (nur bei type="song")
    song_title: str | None
    song_key: str | None        # Tonart
    song_arrangement: str | None
```

### Person-Name Extraktion

EventServices liefern `person` als Domain Object oder `null`:
1. Versuche `person.domainAttributes.firstName + " " + person.domainAttributes.lastName`
2. Fallback auf `person.title`
3. Fallback auf `None` (Slot nicht besetzt → in der Ansicht als "— (offen)" anzeigen)

## Seiten

### Seite 1: Agenda (`/agenda`)

1. Kalenderauswahl + Datumsbereich (gleiche UX wie `/appointments`)
2. Events aus gewählten Kalendern laden und als Liste anzeigen
3. Klick auf ein Event → Agenda wird nachgeladen und aufgeklappt
4. Wenn keine Agenda vorhanden: Hinweis "Keine Agenda vorhanden" statt Fehler
5. Agenda-Items nach `type` unterschiedlich rendern:
   - `header`: als Abschnitts-Überschrift/Separator
   - `song`: mit Tonart und Arrangement
   - `default`: Standard-Darstellung
6. Items mit `isBeforeEvent: true` visuell abgrenzen (z.B. Separator-Linie vor dem "offiziellen" Start)
7. Dauer als MM:SS anzeigen, Startzeiten direkt vom API nutzen
8. Button "Als PDF exportieren" → tabellarische PDF

### Seite 2: Dienstplan (`/services`)

1. Kalenderauswahl + Datumsbereich (gleiche UX)
2. Events mit `?include=eventServices` laden
3. Tabelle: Datum | Event | Dienst | Person | Status (zugesagt/angefragt)
4. Nicht besetzte Slots als "— (offen)" anzeigen
5. Gruppiert nach Event-Datum
6. Button "Als PDF exportieren" → tabellarische PDF

### Navigation

Neue Einträge in der Hauptnavigation (im bestehenden Nav-Partial/Base-Template):
- Termine (bestehend)
- Agenda (neu)
- Dienstplan (neu)

## Interne API-Endpunkte

```
GET /api/events?start_date=...&end_date=...&calendar_ids=...
    → JSON mit EventSummary-Liste (inkl. Services)

GET /api/events/{event_id}/agenda
    → JSON mit AgendaItem-Liste (leer wenn keine Agenda existiert)
```

## PDF-Export

Schlichte, tabellarische PDFs — kein Folien-Styling (Hintergrund, Logo, Farben). Interne Arbeitsunterlagen.

**Agenda-PDF:**
- Titel: "Agenda — Gottesdienst 23.03.2026"
- Tabelle: Zeit | Titel | Dauer | Verantwortlich | Notiz
- Startzeiten direkt vom API (kein manuelles Berechnen)
- Header-Items als Abschnitts-Überschriften
- Song-Items mit Tonart falls vorhanden
- Pre-Event-Items durch Separator-Linie abgegrenzt

**Dienstplan-PDF:**
- Titel: "Dienstplan — 23.03. – 30.03.2026"
- Gruppiert nach Datum/Event
- Tabelle pro Event: Dienst | Person | Status (✓/?)
- Nicht besetzte Slots als "— (offen)"

### Umsetzung

Neue Funktionen im PDF-Generator (ReportLab):
- `create_agenda_pdf(event_name, start_time, agenda_items) → bytes`
- `create_services_pdf(date_range, events_with_services) → bytes`

## Dateistruktur

Folgt den bestehenden Patterns:
- `app/api/events.py` — Routen für beide Seiten (Agenda + Dienstplan)
- `app/templates/agenda.html` — Agenda-Template
- `app/templates/services.html` — Dienstplan-Template
- Neue Client-Funktionen in `app/services/churchtools_client.py`
- Neue PDF-Funktionen in `app/services/pdf_generator.py`
- Neue Pydantic-Modelle in `app/schemas.py`
- Router-Registrierung in `app/main.py`

## Scope-Abgrenzung

- Nur lesender Zugriff auf ChurchTools (kein Schreiben/Ändern)
- Kein Folien-Styling für die neuen PDFs
- Keine automatische Generierung (Cron)
- Kalender-basierte Filterung (Ansatz A), keine separate Event-Typ-Konfiguration
