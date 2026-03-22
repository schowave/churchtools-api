# Agenda & Dienstplan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new pages — Agenda (worship service rundown) and Dienstplan (service assignments) — that read from the ChurchTools Events API and offer simple PDF export.

**Architecture:** New route module `app/api/events.py` serves both pages. New client functions in `churchtools_client.py` call `GET /events` and `GET /events/{id}/agenda`. New PDF functions in `pdf_generator.py` produce tabular A4 PDFs via ReportLab. Templates reuse the existing calendar-selection + date-range UX pattern from appointments.

**Tech Stack:** FastAPI, Jinja2, htmx, Alpine.js, ReportLab, httpx, Pydantic, pytest

**Spec:** `docs/superpowers/specs/2026-03-21-agenda-services-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `app/schemas.py` | Add `EventService`, `EventSummary`, `AgendaItem` Pydantic models |
| Modify | `app/services/churchtools_client.py` | Add `fetch_events()`, `fetch_agenda()`, helper `_extract_person_name()` |
| Create | `app/api/events.py` | Routes: `/agenda`, `/services`, `/api/events`, `/api/events/{id}/agenda`, PDF export endpoints |
| Modify | `app/main.py` | Register `events.router` |
| Create | `app/templates/agenda.html` | Agenda page template |
| Create | `app/templates/services.html` | Services page template |
| ~~Create~~ | ~~`app/templates/fragments/agenda_items.html`~~ | Removed — agenda items are rendered client-side via JSON + JS |
| Modify | `app/templates/overview.html` | Add tiles for Agenda and Dienstplan |
| Modify | `app/services/pdf_generator.py` | Add `create_agenda_pdf()`, `create_services_pdf()` |
| Create | `app/static/css/events.css` | Styles for both new pages |
| Create | `app/static/js/events.js` | JS for event pages (date pickers, HTMX triggers) |
| Create | `tests/test_events.py` | Tests for client functions, routes, models |
| Create | `tests/test_events_pdf.py` | Tests for PDF generation |

---

### Task 1: Pydantic Models

**Files:**
- Modify: `app/schemas.py`
- Create: `tests/test_events.py`

- [ ] **Step 1: Write tests for new models**

In `tests/test_events.py`:

```python
import pytest
from app.schemas import AgendaItem, EventService, EventSummary


def test_event_service_with_person():
    svc = EventService(service_id=1, name="Predigt", person_name="Max Mustermann", is_accepted=True)
    assert svc.name == "Predigt"
    assert svc.person_name == "Max Mustermann"
    assert svc.is_accepted is True


def test_event_service_without_person():
    svc = EventService(service_id=2, name="Worship", person_name=None, is_accepted=False)
    assert svc.person_name is None


def test_event_summary():
    svc = EventService(service_id=1, name="Predigt", person_name="Max", is_accepted=True)
    ev = EventSummary(
        id=42,
        name="Gottesdienst",
        start_date="2026-03-22T09:00:00Z",
        end_date="2026-03-22T11:00:00Z",
        calendar_name="Gottesdienste",
        services=[svc],
    )
    assert ev.id == 42
    assert len(ev.services) == 1


def test_agenda_item_default():
    item = AgendaItem(
        position=1,
        type="default",
        title="Begruessung",
        start="2026-03-22T09:00:00Z",
        duration_seconds=300,
        note="Herzlich willkommen",
        responsible_names=["Max"],
        is_before_event=False,
        song_title=None,
        song_key=None,
        song_arrangement=None,
    )
    assert item.duration_display == "05:00"


def test_agenda_item_song():
    item = AgendaItem(
        position=2,
        type="song",
        title="Amazing Grace",
        start="2026-03-22T09:05:00Z",
        duration_seconds=240,
        note=None,
        responsible_names=["Anna"],
        is_before_event=False,
        song_title="Amazing Grace",
        song_key="G",
        song_arrangement="Band",
    )
    assert item.type == "song"
    assert item.song_key == "G"


def test_agenda_item_header():
    item = AgendaItem(
        position=0,
        type="header",
        title="Vorbereitung",
        start=None,
        duration_seconds=0,
        note=None,
        responsible_names=[],
        is_before_event=True,
        song_title=None,
        song_key=None,
        song_arrangement=None,
    )
    assert item.type == "header"
    assert item.is_before_event is True
    assert item.duration_display == "00:00"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events.py -v`
Expected: FAIL — `ImportError: cannot import name 'EventService' from 'app.schemas'`

- [ ] **Step 3: Implement the models**

Add to `app/schemas.py` (after the existing `GenerateRequest` class):

```python
class EventService(BaseModel):
    """A single service slot within an event (e.g. 'Predigt', 'Worship')."""
    service_id: int
    name: str
    person_name: str | None = None
    is_accepted: bool = False


class EventSummary(BaseModel):
    """An event with its service assignments, used for the Dienstplan view."""
    id: int
    name: str
    start_date: str
    end_date: str
    calendar_name: str
    services: list[EventService] = []


class AgendaItem(BaseModel):
    """A single item in an event's agenda (worship rundown)."""
    position: int
    type: str = "default"  # "default", "song", "header"
    title: str
    start: str | None = None
    duration_seconds: int = 0
    note: str | None = None
    responsible_names: list[str] = []
    is_before_event: bool = False
    song_title: str | None = None
    song_key: str | None = None
    song_arrangement: str | None = None

    @computed_field
    @property
    def duration_display(self) -> str:
        """Format duration as MM:SS."""
        minutes, seconds = divmod(self.duration_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_events.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas.py tests/test_events.py
git commit -m "feat: add Pydantic models for events, agenda, and services"
```

---

### Task 2: ChurchTools Client — fetch_events

**Files:**
- Modify: `app/services/churchtools_client.py`
- Modify: `tests/test_events.py`

- [ ] **Step 1: Write tests for fetch_events**

Append to `tests/test_events.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from app.config import settings
from app.services.churchtools_client import fetch_events, _extract_person_name


@pytest.fixture
def config_mock():
    with (
        patch.object(settings, "churchtools_base", "test.church.tools"),
        patch.object(settings, "churchtools_base_url", "https://test.church.tools"),
    ):
        yield


SAMPLE_EVENTS_RESPONSE = {
    "data": [
        {
            "id": 1,
            "name": "Gottesdienst",
            "startDate": "2026-03-22T09:00:00Z",
            "endDate": "2026-03-22T11:00:00Z",
            "isCanceled": False,
            "calendar": {
                "domainType": "calendar",
                "domainIdentifier": "5",
                "title": "Gottesdienste",
            },
            "eventServices": [
                {
                    "id": 10,
                    "name": "Predigt",
                    "serviceId": 1,
                    "isAccepted": True,
                    "person": {
                        "domainType": "person",
                        "domainIdentifier": "42",
                        "title": "Max Mustermann",
                        "domainAttributes": {
                            "firstName": "Max",
                            "lastName": "Mustermann",
                        },
                    },
                },
                {
                    "id": 11,
                    "name": "Worship",
                    "serviceId": 2,
                    "isAccepted": False,
                    "person": None,
                },
            ],
        },
        {
            "id": 2,
            "name": "Abgesagter Gottesdienst",
            "startDate": "2026-03-29T09:00:00Z",
            "endDate": "2026-03-29T11:00:00Z",
            "isCanceled": True,
            "calendar": {
                "domainType": "calendar",
                "domainIdentifier": "5",
                "title": "Gottesdienste",
            },
            "eventServices": [],
        },
        {
            "id": 3,
            "name": "Jugendkreis",
            "startDate": "2026-03-22T18:00:00Z",
            "endDate": "2026-03-22T20:00:00Z",
            "isCanceled": False,
            "calendar": {
                "domainType": "calendar",
                "domainIdentifier": "8",
                "title": "Jugend",
            },
            "eventServices": [],
        },
    ]
}


@pytest.mark.asyncio
async def test_fetch_events_filters_by_calendar_and_canceled(config_mock):
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = SAMPLE_EVENTS_RESPONSE
    client.get.return_value = response

    result = await fetch_events("token", "2026-03-22", "2026-03-29", ["5"], client)

    # Should include event 1 (calendar 5, not canceled)
    # Should exclude event 2 (canceled)
    # Should exclude event 3 (calendar 8, not in filter)
    assert len(result) == 1
    assert result[0].id == 1
    assert result[0].name == "Gottesdienst"
    assert result[0].calendar_name == "Gottesdienste"
    assert len(result[0].services) == 2
    assert result[0].services[0].person_name == "Max Mustermann"
    assert result[0].services[0].is_accepted is True
    assert result[0].services[1].person_name is None


@pytest.mark.asyncio
async def test_fetch_events_all_calendars(config_mock):
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = SAMPLE_EVENTS_RESPONSE
    client.get.return_value = response

    result = await fetch_events("token", "2026-03-22", "2026-03-29", ["5", "8"], client)

    # Event 1 and 3 (not canceled, matching calendars)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_fetch_events_auth_error(config_mock):
    from app.services.churchtools_client import AuthenticationError

    client = AsyncMock()
    response = MagicMock()
    response.status_code = 401
    client.get.return_value = response

    with pytest.raises(AuthenticationError):
        await fetch_events("bad_token", "2026-03-22", "2026-03-29", ["5"], client)


def test_extract_person_name_full():
    person = {
        "title": "Max Mustermann",
        "domainAttributes": {"firstName": "Max", "lastName": "Mustermann"},
    }
    assert _extract_person_name(person) == "Max Mustermann"


def test_extract_person_name_title_fallback():
    person = {"title": "Max M.", "domainAttributes": {}}
    assert _extract_person_name(person) == "Max M."


def test_extract_person_name_none():
    assert _extract_person_name(None) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events.py::test_fetch_events_filters_by_calendar_and_canceled -v`
Expected: FAIL — `ImportError: cannot import name 'fetch_events'`

- [ ] **Step 3: Implement fetch_events and _extract_person_name**

Add to `app/services/churchtools_client.py`:

```python
from datetime import datetime, timedelta

from app.schemas import AgendaItem, EventService, EventSummary

def _extract_person_name(person: dict | None) -> str | None:
    """Extract display name from a person domain object."""
    if person is None:
        return None
    attrs = person.get("domainAttributes", {})
    first = attrs.get("firstName", "")
    last = attrs.get("lastName", "")
    if first and last:
        return f"{first} {last}"
    return person.get("title") or None


async def fetch_events(
    login_token: str,
    start_date: str,
    end_date: str,
    calendar_ids: list[str],
    client: httpx.AsyncClient,
) -> list[EventSummary]:
    """Fetch events from ChurchTools, filtered by calendar IDs. Canceled events are excluded."""
    url = f"{settings.churchtools_base_url}/api/events"
    # Add +1 day to end_date: the API's `to` is currently inclusive but will become
    # exclusive in a future version. Adding a day makes us forward-compatible.
    to_date = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    params = {"from": start_date, "to": to_date, "include": "eventServices"}
    response = await client.get(url, headers=_auth_headers(login_token), params=params)

    if response.status_code in (401, 403):
        raise AuthenticationError("Login token is invalid or expired")
    response.raise_for_status()

    calendar_ids_set = set(calendar_ids)
    events = []
    for item in response.json().get("data", []):
        if item.get("isCanceled", False):
            continue
        cal = item.get("calendar", {})
        if cal.get("domainIdentifier") not in calendar_ids_set:
            continue

        services = []
        for svc in item.get("eventServices", []):
            services.append(
                EventService(
                    service_id=svc.get("serviceId", svc.get("id", 0)),
                    name=svc.get("name", ""),
                    person_name=_extract_person_name(svc.get("person")),
                    is_accepted=svc.get("isAccepted", False),
                )
            )

        events.append(
            EventSummary(
                id=item["id"],
                name=item.get("name", ""),
                start_date=item.get("startDate", ""),
                end_date=item.get("endDate", ""),
                calendar_name=cal.get("title", ""),
                services=services,
            )
        )

    return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_events.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/churchtools_client.py tests/test_events.py
git commit -m "feat: add fetch_events with calendar filtering and person name extraction"
```

---

### Task 3: ChurchTools Client — fetch_agenda

**Files:**
- Modify: `app/services/churchtools_client.py`
- Modify: `tests/test_events.py`

- [ ] **Step 1: Write tests for fetch_agenda**

Append to `tests/test_events.py`:

```python
from app.services.churchtools_client import fetch_agenda


SAMPLE_AGENDA_RESPONSE = {
    "data": {
        "id": 10,
        "calendarId": 5,
        "isLocked": False,
        "items": [
            {
                "type": "default",
                "position": 1,
                "title": "Begruessung",
                "start": "2026-03-22T09:00:00Z",
                "duration": 300,
                "note": "Herzlich willkommen",
                "isBeforeEvent": False,
                "responsible": {
                    "text": "Max Mustermann",
                    "persons": [
                        {
                            "accepted": True,
                            "person": {
                                "title": "Max Mustermann",
                                "domainAttributes": {"firstName": "Max", "lastName": "Mustermann"},
                            },
                        }
                    ],
                },
            },
            {
                "type": "song",
                "position": 2,
                "title": "Amazing Grace",
                "start": "2026-03-22T09:05:00Z",
                "duration": 240,
                "note": None,
                "isBeforeEvent": False,
                "responsible": {"text": "", "persons": []},
                "song": {
                    "title": "Amazing Grace",
                    "arrangement": "Band Version",
                    "key": "G",
                },
            },
            {
                "type": "header",
                "position": 0,
                "title": "Vorbereitung",
                "isBeforeEvent": True,
            },
        ],
    }
}


@pytest.mark.asyncio
async def test_fetch_agenda_success(config_mock):
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = SAMPLE_AGENDA_RESPONSE
    client.get.return_value = response

    result = await fetch_agenda("token", 1, client)

    assert len(result) == 3
    # Check default item
    default_item = [i for i in result if i.type == "default"][0]
    assert default_item.title == "Begruessung"
    assert default_item.duration_seconds == 300
    assert default_item.responsible_names == ["Max Mustermann"]
    assert default_item.note == "Herzlich willkommen"

    # Check song item
    song_item = [i for i in result if i.type == "song"][0]
    assert song_item.song_title == "Amazing Grace"
    assert song_item.song_key == "G"
    assert song_item.song_arrangement == "Band Version"

    # Check header item
    header_item = [i for i in result if i.type == "header"][0]
    assert header_item.is_before_event is True
    assert header_item.duration_seconds == 0


@pytest.mark.asyncio
async def test_fetch_agenda_not_found(config_mock):
    """Events without an agenda return 404 — function should return empty list."""
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 404
    client.get.return_value = response

    result = await fetch_agenda("token", 999, client)
    assert result == []


@pytest.mark.asyncio
async def test_fetch_agenda_auth_error(config_mock):
    from app.services.churchtools_client import AuthenticationError

    client = AsyncMock()
    response = MagicMock()
    response.status_code = 401
    client.get.return_value = response

    with pytest.raises(AuthenticationError):
        await fetch_agenda("bad_token", 1, client)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events.py::test_fetch_agenda_success -v`
Expected: FAIL — `ImportError: cannot import name 'fetch_agenda'`

- [ ] **Step 3: Implement fetch_agenda**

Add to `app/services/churchtools_client.py`:

```python
async def fetch_agenda(
    login_token: str,
    event_id: int,
    client: httpx.AsyncClient,
) -> list[AgendaItem]:
    """Fetch the agenda for an event. Returns empty list if no agenda exists (404)."""
    url = f"{settings.churchtools_base_url}/api/events/{event_id}/agenda"
    response = await client.get(url, headers=_auth_headers(login_token))

    if response.status_code == 404:
        return []
    if response.status_code in (401, 403):
        raise AuthenticationError("Login token is invalid or expired")
    response.raise_for_status()

    data = response.json().get("data", {})
    items = []
    for raw_item in data.get("items", []):
        item_type = raw_item.get("type", "default")

        # Extract responsible person names
        responsible_names = []
        responsible = raw_item.get("responsible", {})
        for entry in responsible.get("persons", []):
            name = _extract_person_name(entry.get("person"))
            if name:
                responsible_names.append(name)

        # Extract song info
        song = raw_item.get("song", {}) or {}

        items.append(
            AgendaItem(
                position=raw_item.get("position", 0),
                type=item_type if item_type in ("default", "song", "header") else "default",
                title=raw_item.get("title", ""),
                start=raw_item.get("start"),
                duration_seconds=raw_item.get("duration", 0),
                note=raw_item.get("note"),
                responsible_names=responsible_names,
                is_before_event=raw_item.get("isBeforeEvent", False),
                song_title=song.get("title"),
                song_key=song.get("key"),
                song_arrangement=song.get("arrangement"),
            )
        )

    return items
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_events.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/churchtools_client.py tests/test_events.py
git commit -m "feat: add fetch_agenda with 404 handling and song/header support"
```

---

### Task 4: API Routes — Events & Agenda JSON Endpoints

**Files:**
- Create: `app/api/events.py`
- Modify: `app/main.py`
- Modify: `tests/test_events.py`

- [ ] **Step 1: Write tests for JSON endpoints**

Append to `tests/test_events.py`:

```python
from app.api.events import api_events, api_event_agenda


@pytest.fixture
def templates_mock():
    from unittest.mock import patch as _patch
    from fastapi.templating import Jinja2Templates

    mock = MagicMock(spec=Jinja2Templates)
    with _patch("app.api.events.templates", mock):
        yield mock


@pytest.mark.asyncio
@patch("app.api.events.fetch_events")
async def test_api_events_success(mock_fetch, config_mock):
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "token"
    client = AsyncMock()

    mock_fetch.return_value = [
        EventSummary(
            id=1, name="Gottesdienst", start_date="2026-03-22T09:00:00Z",
            end_date="2026-03-22T11:00:00Z", calendar_name="GD",
            services=[EventService(service_id=1, name="Predigt", person_name="Max", is_accepted=True)],
        )
    ]

    response = await api_events(
        request=request, client=client,
        start_date="2026-03-22", end_date="2026-03-29", calendar_ids=["5"],
    )

    assert response.status_code == 200
    mock_fetch.assert_called_once_with("token", "2026-03-22", "2026-03-29", ["5"], client)


@pytest.mark.asyncio
async def test_api_events_no_auth(config_mock):
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = None
    client = AsyncMock()

    response = await api_events(
        request=request, client=client,
        start_date="2026-03-22", end_date="2026-03-29", calendar_ids=["5"],
    )

    assert response.status_code == 401


@pytest.mark.asyncio
@patch("app.api.events.fetch_agenda")
async def test_api_event_agenda_success(mock_fetch, config_mock):
    from fastapi import Request
    from app.schemas import AgendaItem

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "token"
    client = AsyncMock()

    mock_fetch.return_value = [
        AgendaItem(position=1, type="default", title="Begruessung",
                   start="2026-03-22T09:00:00Z", duration_seconds=300,
                   responsible_names=["Max"], is_before_event=False),
    ]

    response = await api_event_agenda(request=request, event_id=1, client=client)

    assert response.status_code == 200
    mock_fetch.assert_called_once_with("token", 1, client)


@pytest.mark.asyncio
@patch("app.api.events.fetch_agenda")
async def test_api_event_agenda_empty(mock_fetch, config_mock):
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "token"
    client = AsyncMock()
    mock_fetch.return_value = []

    response = await api_event_agenda(request=request, event_id=999, client=client)

    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events.py::test_api_events_success -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.events'`

- [ ] **Step 3: Create app/api/events.py with JSON endpoints**

Create `app/api/events.py`:

```python
from typing import List, Optional

import httpx
import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette import status

from app.config import settings
from app.dependencies import get_http_client
from app.services.churchtools_client import (
    AuthenticationError,
    fetch_agenda,
    fetch_calendars,
    fetch_events,
)
from app.shared import templates
from app.utils import get_date_range_from_form

logger = structlog.get_logger()
router = APIRouter()


@router.get("/api/events")
async def api_events(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: str = Query(...),
    end_date: str = Query(...),
    calendar_ids: List[str] = Query(...),
) -> JSONResponse:
    """JSON endpoint returning events with their service assignments."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    try:
        events = await fetch_events(login_token, start_date, end_date, calendar_ids, client)
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    return JSONResponse({"events": [ev.model_dump() for ev in events]})


@router.get("/api/events/{event_id}/agenda")
async def api_event_agenda(
    request: Request,
    event_id: int,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> JSONResponse:
    """JSON endpoint returning the agenda for a single event."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    try:
        items = await fetch_agenda(login_token, event_id, client)
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    return JSONResponse({"items": [item.model_dump() for item in items]})
```

- [ ] **Step 4: Register the router in app/main.py**

Add to `app/main.py` imports:

```python
from app.api import appointments, auth, events, fragments, health
```

And add the router:

```python
app.include_router(events.router, tags=["events"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_events.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/api/events.py app/main.py tests/test_events.py
git commit -m "feat: add JSON API endpoints for events and agenda"
```

---

### Task 5: Page Routes — Agenda & Services HTML Pages

**Files:**
- Modify: `app/api/events.py`
- Create: `app/templates/agenda.html`
- Create: `app/templates/services.html`
- Create: `app/static/css/events.css`
- Create: `app/static/js/events.js`

- [ ] **Step 1: Add page routes to app/api/events.py**

Add these routes to `app/api/events.py`:

```python
@router.get("/agenda")
async def agenda_page(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    calendar_ids: Optional[List[str]] = Query(None),
) -> Response:
    """Agenda page — shows worship service rundowns."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    if not start_date or not end_date:
        start_date_default, end_date_default = get_date_range_from_form()
        start_date = start_date or start_date_default
        end_date = end_date or end_date_default

    try:
        calendars = await fetch_calendars(login_token, client)
    except AuthenticationError:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(key=settings.cookie_login_token)
        return response

    if calendar_ids:
        selected_calendar_ids = calendar_ids
    else:
        selected_calendar_ids = [str(cal["id"]) for cal in calendars]

    return templates.TemplateResponse(
        "agenda.html",
        {
            "request": request,
            "calendars": calendars,
            "selected_calendar_ids": selected_calendar_ids,
            "start_date": start_date,
            "end_date": end_date,
            "base_url": settings.churchtools_base,
            "version": settings.version,
        },
    )


@router.get("/services")
async def services_page(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    calendar_ids: Optional[List[str]] = Query(None),
) -> Response:
    """Dienstplan page — shows who does what per event."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    if not start_date or not end_date:
        start_date_default, end_date_default = get_date_range_from_form()
        start_date = start_date or start_date_default
        end_date = end_date or end_date_default

    try:
        calendars = await fetch_calendars(login_token, client)
    except AuthenticationError:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(key=settings.cookie_login_token)
        return response

    if calendar_ids:
        selected_calendar_ids = calendar_ids
    else:
        selected_calendar_ids = [str(cal["id"]) for cal in calendars]

    return templates.TemplateResponse(
        "services.html",
        {
            "request": request,
            "calendars": calendars,
            "selected_calendar_ids": selected_calendar_ids,
            "start_date": start_date,
            "end_date": end_date,
            "base_url": settings.churchtools_base,
            "version": settings.version,
        },
    )
```

- [ ] **Step 2: Create agenda.html template**

Create `app/templates/agenda.html`. Follow the same structure as `appointments.html`:
- Same `<head>` with common CSS + events.css + flatpickr
- Same page header pattern with back-link to `/overview`
- Same search-card with date-range inputs + calendar chips
- Results area: a `<div id="events-list">` where JS loads events via `/api/events`, then each event is expandable to show its agenda items via `/api/events/{id}/agenda`
- Export button that triggers `/api/events/{id}/agenda/pdf`

Key template structure:
```html
<!-- Events list populated by JS -->
<div id="events-list" class="events-list">
    <p class="events-loading">Lade Events...</p>
</div>
```

The JS (`events.js`) fetches events and renders them as expandable cards. Clicking a card fetches the agenda and shows it inline.

- [ ] **Step 3: Create services.html template**

Create `app/templates/services.html`. Same structure as agenda.html but:
- Results area shows a table of all services across all events
- Grouped by event date
- Columns: Event | Dienst | Person | Status

- [ ] **Step 4: Create events.css**

Create `app/static/css/events.css` reusing CSS variables and patterns from `common.css` and `appointments.css`:
- `.events-list` — container for event cards
- `.event-card` — collapsible card (for agenda page)
- `.event-card-header` — clickable header
- `.agenda-table` — table for agenda items inside expanded card
- `.agenda-header-row` — styled differently for header-type items
- `.agenda-song-info` — key/arrangement info
- `.services-table` — table for dienstplan view
- `.status-accepted` / `.status-pending` — status badges

- [ ] **Step 5: Create events.js**

Create `app/static/js/events.js`:
- On DOMContentLoaded, initialize flatpickr date pickers (same pattern as appointments.js)
- `loadEvents()` function: reads date + calendar selections, fetches `/api/events?...`, renders event cards
- For agenda page: click handler on event cards that fetches `/api/events/{id}/agenda` and renders agenda table
- For services page: events are already loaded with services, just render the table
- Export buttons trigger the PDF download endpoints

- [ ] **Step 6: Verify pages render (manual check)**

Run: `make run`
Navigate to `/agenda` and `/services` — verify they load without errors, show calendar selection, date pickers work.

- [ ] **Step 7: Commit**

```bash
git add app/api/events.py app/templates/agenda.html app/templates/services.html app/static/css/events.css app/static/js/events.js
git commit -m "feat: add agenda and services pages with calendar selection and event loading"
```

---

### Task 6: Navigation — Update Overview Page

**Files:**
- Modify: `app/templates/overview.html`

- [ ] **Step 1: Add tiles for Agenda and Dienstplan**

In `app/templates/overview.html`, after the existing `<a href="/appointments" class="tile">` block, add two new tiles:

```html
<a href="/agenda" class="tile">
    <span class="tile-icon">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
        </svg>
    </span>
    Agenda
</a>
<a href="/services" class="tile">
    <span class="tile-icon">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
    </span>
    Dienstplan
</a>
```

- [ ] **Step 2: Verify navigation works (manual)**

Run: `make run`
Navigate to `/overview` — verify both new tiles appear and link correctly.

- [ ] **Step 3: Commit**

```bash
git add app/templates/overview.html
git commit -m "feat: add agenda and services tiles to overview page"
```

---

### Task 7: PDF Export — Agenda PDF

**Files:**
- Modify: `app/services/pdf_generator.py`
- Create: `tests/test_events_pdf.py`

- [ ] **Step 1: Write tests for create_agenda_pdf**

Create `tests/test_events_pdf.py`:

```python
import pytest
from app.schemas import AgendaItem
from app.services.pdf_generator import create_agenda_pdf


def _make_agenda_items():
    return [
        AgendaItem(
            position=0, type="header", title="Vorbereitung",
            start=None, duration_seconds=0, responsible_names=[],
            is_before_event=True,
        ),
        AgendaItem(
            position=1, type="default", title="Begruessung",
            start="2026-03-22T09:00:00Z", duration_seconds=300,
            note="Herzlich willkommen", responsible_names=["Max Mustermann"],
            is_before_event=False,
        ),
        AgendaItem(
            position=2, type="song", title="Amazing Grace",
            start="2026-03-22T09:05:00Z", duration_seconds=240,
            responsible_names=["Anna"], is_before_event=False,
            song_title="Amazing Grace", song_key="G", song_arrangement="Band",
        ),
    ]


def test_create_agenda_pdf_returns_bytes():
    items = _make_agenda_items()
    result = create_agenda_pdf("Gottesdienst", "2026-03-22T09:00:00Z", items)
    assert isinstance(result, bytes)
    assert result[:5] == b"%PDF-"


def test_create_agenda_pdf_empty_items():
    result = create_agenda_pdf("Gottesdienst", "2026-03-22T09:00:00Z", [])
    assert isinstance(result, bytes)
    assert result[:5] == b"%PDF-"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events_pdf.py -v`
Expected: FAIL — `ImportError: cannot import name 'create_agenda_pdf'`

- [ ] **Step 3: Implement create_agenda_pdf**

Add to `app/services/pdf_generator.py`:

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.schemas import AgendaItem


def create_agenda_pdf(event_name: str, event_start: str, agenda_items: list[AgendaItem]) -> bytes:
    """Create a tabular A4 PDF for a worship service agenda."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=15*mm,
                            leftMargin=15*mm, rightMargin=15*mm)

    font_name, font_name_bold = _register_fonts()
    styles = getSampleStyleSheet()

    # Use unique style names to avoid ReportLab's global registry collision
    title_style = ParagraphStyle("AgendaTitle", parent=styles["Heading1"],
                                  fontName=font_name_bold, fontSize=16, spaceAfter=6)
    subtitle_style = ParagraphStyle("AgendaSubtitle", parent=styles["Normal"],
                                     fontName=font_name, fontSize=10, textColor=colors.grey,
                                     spaceAfter=12)
    cell_style = ParagraphStyle("AgendaCell", parent=styles["Normal"],
                                 fontName=font_name, fontSize=9, leading=12)
    header_cell_style = ParagraphStyle("AgendaHeaderCell", parent=styles["Normal"],
                                        fontName=font_name_bold, fontSize=9, leading=12,
                                        textColor=colors.white)
    section_style = ParagraphStyle("AgendaSection", parent=styles["Normal"],
                                    fontName=font_name_bold, fontSize=10, leading=14,
                                    textColor=colors.HexColor("#5E8B5A"))

    start_dt = parse_iso_datetime(event_start)
    date_str = start_dt.strftime("%d.%m.%Y")

    elements = []
    elements.append(Paragraph(f"Agenda — {event_name}", title_style))
    elements.append(Paragraph(date_str, subtitle_style))

    # Build table data
    table_data = [["Zeit", "Titel", "Dauer", "Verantwortlich", "Notiz"]]
    row_styles = []

    for item in agenda_items:
        if item.type == "header":
            # Header rows span all columns
            table_data.append([Paragraph(item.title, section_style), "", "", "", ""])
            row_idx = len(table_data) - 1
            row_styles.append(("SPAN", (0, row_idx), (4, row_idx)))
            row_styles.append(("BACKGROUND", (0, row_idx), (4, row_idx), colors.HexColor("#F0F3ED")))
            continue

        time_str = ""
        if item.start:
            dt = parse_iso_datetime(item.start)
            time_str = dt.strftime("%H:%M")

        title = item.title
        if item.type == "song" and item.song_key:
            title += f" ({item.song_key})"
            if item.song_arrangement:
                title += f"\n{item.song_arrangement}"

        table_data.append([
            Paragraph(time_str, cell_style),
            Paragraph(title.replace("\n", "<br/>"), cell_style),
            Paragraph(item.duration_display, cell_style),
            Paragraph(", ".join(item.responsible_names) if item.responsible_names else "", cell_style),
            Paragraph(item.note or "", cell_style),
        ])

    if len(table_data) > 1:
        col_widths = [45, 150, 40, 100, None]  # None = auto-fill remaining
        available = A4[0] - 30*mm
        fixed = sum(w for w in col_widths if w is not None)
        col_widths[-1] = available - fixed

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        base_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5E8B5A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), font_name_bold),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8DDD0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFBF8")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        base_style.extend(row_styles)
        table.setStyle(TableStyle(base_style))
        elements.append(table)

    doc.build(elements)
    return buffer.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_events_pdf.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/pdf_generator.py tests/test_events_pdf.py
git commit -m "feat: add tabular agenda PDF generation"
```

---

### Task 8: PDF Export — Services PDF

**Files:**
- Modify: `app/services/pdf_generator.py`
- Modify: `tests/test_events_pdf.py`

- [ ] **Step 1: Write tests for create_services_pdf**

Append to `tests/test_events_pdf.py`:

```python
from app.schemas import EventService, EventSummary
from app.services.pdf_generator import create_services_pdf


def _make_events():
    return [
        EventSummary(
            id=1, name="Gottesdienst", start_date="2026-03-22T09:00:00Z",
            end_date="2026-03-22T11:00:00Z", calendar_name="GD",
            services=[
                EventService(service_id=1, name="Predigt", person_name="Max Mustermann", is_accepted=True),
                EventService(service_id=2, name="Worship", person_name=None, is_accepted=False),
            ],
        ),
        EventSummary(
            id=2, name="Abendgottesdienst", start_date="2026-03-22T18:00:00Z",
            end_date="2026-03-22T19:30:00Z", calendar_name="GD",
            services=[
                EventService(service_id=1, name="Predigt", person_name="Anna Schmidt", is_accepted=True),
            ],
        ),
    ]


def test_create_services_pdf_returns_bytes():
    events = _make_events()
    result = create_services_pdf("22.03. – 29.03.2026", events)
    assert isinstance(result, bytes)
    assert result[:5] == b"%PDF-"


def test_create_services_pdf_empty_events():
    result = create_services_pdf("22.03. – 29.03.2026", [])
    assert isinstance(result, bytes)
    assert result[:5] == b"%PDF-"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events_pdf.py::test_create_services_pdf_returns_bytes -v`
Expected: FAIL — `ImportError: cannot import name 'create_services_pdf'`

- [ ] **Step 3: Implement create_services_pdf**

Add to `app/services/pdf_generator.py`:

```python
from app.schemas import EventSummary


def create_services_pdf(date_range: str, events: list[EventSummary]) -> bytes:
    """Create a tabular A4 PDF for service assignments across events."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=15*mm,
                            leftMargin=15*mm, rightMargin=15*mm)

    font_name, font_name_bold = _register_fonts()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("ServicesTitle", parent=styles["Heading1"],
                                  fontName=font_name_bold, fontSize=16, spaceAfter=6)
    subtitle_style = ParagraphStyle("ServicesSubtitle", parent=styles["Normal"],
                                     fontName=font_name, fontSize=10, textColor=colors.grey,
                                     spaceAfter=12)
    cell_style = ParagraphStyle("ServicesCell", parent=styles["Normal"],
                                 fontName=font_name, fontSize=9, leading=12)
    event_header_style = ParagraphStyle("ServicesEventHeader", parent=styles["Normal"],
                                         fontName=font_name_bold, fontSize=10, leading=14)

    elements = []
    elements.append(Paragraph(f"Dienstplan — {date_range}", title_style))
    elements.append(Spacer(1, 6))

    for event in events:
        start_dt = parse_iso_datetime(event.start_date)
        event_label = f"{start_dt.strftime('%d.%m.%Y %H:%M')} — {event.name}"
        elements.append(Paragraph(event_label, event_header_style))
        elements.append(Spacer(1, 4))

        if not event.services:
            elements.append(Paragraph("Keine Dienste eingetragen", cell_style))
            elements.append(Spacer(1, 10))
            continue

        table_data = [["Dienst", "Person", "Status"]]
        for svc in event.services:
            person = svc.person_name or "— (offen)"
            status_str = "\u2713" if svc.is_accepted else "?"
            table_data.append([
                Paragraph(svc.name, cell_style),
                Paragraph(person, cell_style),
                Paragraph(status_str, cell_style),
            ])

        available = A4[0] - 30*mm
        col_widths = [available * 0.35, available * 0.45, available * 0.20]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5E8B5A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), font_name_bold),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8DDD0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFBF8")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 14))

    doc.build(elements)
    return buffer.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_events_pdf.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/pdf_generator.py tests/test_events_pdf.py
git commit -m "feat: add tabular services PDF generation"
```

---

### Task 9: PDF Export Routes

**Files:**
- Modify: `app/api/events.py`
- Modify: `tests/test_events.py`

- [ ] **Step 1: Write tests for PDF export endpoints**

Append to `tests/test_events.py`:

```python
from app.api.events import api_agenda_pdf, api_services_pdf


@pytest.mark.asyncio
@patch("app.api.events.create_agenda_pdf")
@patch("app.api.events.fetch_agenda")
async def test_api_agenda_pdf(mock_fetch_agenda, mock_create_pdf, config_mock):
    from fastapi import Request
    from fastapi.responses import StreamingResponse

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "token"
    client = AsyncMock()

    mock_fetch_agenda.return_value = [
        AgendaItem(position=1, type="default", title="Begruessung",
                   start="2026-03-22T09:00:00Z", duration_seconds=300,
                   responsible_names=["Max"], is_before_event=False),
    ]
    mock_create_pdf.return_value = b"%PDF-1.4 fake"

    response = await api_agenda_pdf(
        request=request, event_id=1, event_name="Gottesdienst",
        event_start="2026-03-22T09:00:00Z", client=client,
    )

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "application/pdf"


@pytest.mark.asyncio
@patch("app.api.events.create_services_pdf")
@patch("app.api.events.fetch_events")
async def test_api_services_pdf(mock_fetch_events, mock_create_pdf, config_mock):
    from fastapi import Request
    from fastapi.responses import StreamingResponse

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "token"
    client = AsyncMock()

    mock_fetch_events.return_value = [
        EventSummary(id=1, name="GD", start_date="2026-03-22T09:00:00Z",
                     end_date="2026-03-22T11:00:00Z", calendar_name="GD", services=[]),
    ]
    mock_create_pdf.return_value = b"%PDF-1.4 fake"

    response = await api_services_pdf(
        request=request, client=client,
        start_date="2026-03-22", end_date="2026-03-29", calendar_ids=["5"],
    )

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "application/pdf"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events.py::test_api_agenda_pdf -v`
Expected: FAIL — `ImportError: cannot import name 'api_agenda_pdf'`

- [ ] **Step 3: Add PDF export routes to app/api/events.py**

Add to `app/api/events.py`:

```python
from io import BytesIO
from datetime import datetime
from fastapi.responses import StreamingResponse
from app.services.pdf_generator import create_agenda_pdf, create_services_pdf


@router.get("/api/events/{event_id}/agenda/pdf")
async def api_agenda_pdf(
    request: Request,
    event_id: int,
    event_name: str = Query(...),
    event_start: str = Query(...),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Response:
    """Generate and download an agenda PDF for a single event."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    try:
        items = await fetch_agenda(login_token, event_id, client)
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    pdf_bytes = create_agenda_pdf(event_name, event_start, items)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={timestamp}_agenda.pdf"},
    )


@router.get("/api/services/pdf")
async def api_services_pdf(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: str = Query(...),
    end_date: str = Query(...),
    calendar_ids: List[str] = Query(...),
) -> Response:
    """Generate and download a services PDF for the selected date range."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    try:
        events = await fetch_events(login_token, start_date, end_date, calendar_ids, client)
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    # Format date range for PDF title — use strptime directly to avoid
    # timezone-related date shifts (we only need the date, not the time)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    date_range = f"{start_dt.strftime('%d.%m.')} – {end_dt.strftime('%d.%m.%Y')}"

    pdf_bytes = create_services_pdf(date_range, events)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={timestamp}_dienstplan.pdf"},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_events.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/events.py tests/test_events.py
git commit -m "feat: add PDF export endpoints for agenda and services"
```

---

### Task 10: Full Integration Test

**Files:**
- Modify: `tests/test_events.py`

- [ ] **Step 1: Run entire test suite**

Run: `pytest -v`
Expected: All existing + new tests PASS. No regressions in existing appointment tests.

- [ ] **Step 2: Run linter**

Run: `make lint`
Expected: No errors. Fix any issues found.

- [ ] **Step 3: Manual smoke test**

Run: `make run`

Verify:
1. `/overview` shows three tiles (Folienerstellung, Agenda, Dienstplan)
2. `/agenda` loads, shows calendar selection and date pickers
3. `/services` loads, shows calendar selection and date pickers
4. Existing `/appointments` still works as before

- [ ] **Step 4: Commit any final fixes**

```bash
# Only add specific files that were changed — avoid git add -A
git add <changed-files>
git commit -m "chore: lint fixes and integration verification"
```

---

## Notes for Implementing Agent

1. **Imports:** When appending tests across multiple tasks to `tests/test_events.py`, consolidate all imports at the top of the file. Don't duplicate `from unittest.mock import ...` etc.
2. **Calendar IDs:** Events use string calendar IDs (`calendar.domainIdentifier`) while the existing appointments code uses integer calendar IDs. This is intentional — the Events API uses Domain Objects, the Calendars API uses numeric IDs.
3. **Staged file:** `openapi.json` is currently staged but uncommitted. Don't include it in feature commits — either commit it separately first or unstage it.
4. **Template/JS code:** Tasks 5-6 describe templates and JS in prose rather than exact code. Follow the patterns in `appointments.html` and `app/static/js/appointments.js` closely. The implementing agent should read those files before creating the new ones.
