# Agenda & Dienstplan — Design Spec

## Problem

Die App nutzt aktuell nur Kalender-Termine aus der ChurchTools API, um Ankündigungsfolien zu generieren. Für das Medienteam fehlen zwei häufig benötigte Ansichten: der Gottesdienst-Ablaufplan (Agenda) und die Dienstplan-Übersicht (wer macht was).

## Lösung

Zwei neue eigenständige Seiten in der bestehenden App, die weitere ChurchTools-API-Endpunkte nutzen.

## Datenmodell

### Neue ChurchTools-Client-Funktionen

**Events laden:**
- `fetch_events(login_token, from, to, calendar_ids, client)` → `GET /events?from=...&to=...&include=eventServices`
- Client-seitige Filterung nach ausgewählten Kalender-IDs (API bietet keinen Kalender-Filter)
- Rückgabe pro Event: `id`, `name`, `startDate`, `endDate`, `calendar`, `eventServices[]`

**Agenda laden:**
- `fetch_agenda(login_token, event_id, client)` → `GET /events/{eventId}/agenda`
- Rückgabe: Liste von Agenda-Items mit `position`, `title`, `duration` (Sekunden), `note`, `responsible.persons[]`, Song-Referenz

### Pydantic-Modelle

```python
class EventService:
    name: str           # z.B. "Predigt", "Worship-Leitung"
    person_name: str    # Name der zugewiesenen Person
    is_accepted: bool   # Zugesagt?

class EventSummary:
    id: int
    name: str
    start_date: str
    end_date: str
    calendar_name: str
    services: list[EventService]

class AgendaItem:
    position: int
    title: str
    duration_minutes: int
    note: str | None
    responsible_names: list[str]
    song_title: str | None
```

## Seiten

### Seite 1: Agenda (`/agenda`)

1. Kalenderauswahl + Datumsbereich (gleiche UX wie `/appointments`)
2. Events aus gewählten Kalendern laden und als Liste anzeigen
3. Klick auf ein Event → Agenda wird nachgeladen und aufgeklappt
4. Agenda zeigt: Position, Titel, Dauer, Verantwortliche, Song-Titel, Notizen
5. Button "Als PDF exportieren" → tabellarische PDF

### Seite 2: Dienstplan (`/services`)

1. Kalenderauswahl + Datumsbereich (gleiche UX)
2. Events mit `?include=eventServices` laden
3. Tabelle: Datum | Event | Dienst | Person | Status (zugesagt/angefragt)
4. Gruppiert nach Event-Datum
5. Button "Als PDF exportieren" → tabellarische PDF

### Navigation

Neue Einträge in der Hauptnavigation:
- Termine (bestehend)
- Agenda (neu)
- Dienstplan (neu)

## Interne API-Endpunkte

```
GET /api/events?start_date=...&end_date=...&calendar_ids=...
    → JSON mit EventSummary-Liste (inkl. Services)

GET /api/events/{event_id}/agenda
    → JSON mit AgendaItem-Liste
```

## PDF-Export

Schlichte, tabellarische PDFs — kein Folien-Styling (Hintergrund, Logo, Farben). Interne Arbeitsunterlagen.

**Agenda-PDF:**
- Titel: "Agenda — Gottesdienst 23.03.2026"
- Tabelle: Zeit | Titel | Dauer | Verantwortlich | Notiz
- Zeiten berechnet aus Event-Start + kumulierten Dauern
- Song-Titel als eigene Spalte falls vorhanden

**Dienstplan-PDF:**
- Titel: "Dienstplan — 23.03. – 30.03.2026"
- Gruppiert nach Datum/Event
- Tabelle pro Event: Dienst | Person | Status (✓/?)

### Umsetzung

Neue Funktionen im PDF-Generator (ReportLab):
- `create_agenda_pdf(event_name, start_time, agenda_items) → bytes`
- `create_services_pdf(date_range, events_with_services) → bytes`

## Scope-Abgrenzung

- Nur lesender Zugriff auf ChurchTools (kein Schreiben/Ändern)
- Kein Folien-Styling für die neuen PDFs
- Keine automatische Generierung (Cron)
- Kalender-basierte Filterung (Ansatz A), keine separate Event-Typ-Konfiguration
