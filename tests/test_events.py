from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.events import api_agenda_pdf, api_event_agenda, api_event_services_pdf, api_events
from app.config import settings
from app.schemas import AgendaItem, EventService, EventSummary
from app.services.churchtools_client import _extract_person_name, fetch_agenda, fetch_events


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


# ---------------------------------------------------------------------------
# Task 2: fetch_events + _extract_person_name
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Task 3: fetch_agenda
# ---------------------------------------------------------------------------


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
    default_item = [i for i in result if i.type == "default"][0]
    assert default_item.title == "Begruessung"
    assert default_item.duration_seconds == 300
    assert default_item.responsible_names == ["Max Mustermann"]
    assert default_item.note == "Herzlich willkommen"

    song_item = [i for i in result if i.type == "song"][0]
    assert song_item.song_title == "Amazing Grace"
    assert song_item.song_key == "G"
    assert song_item.song_arrangement == "Band Version"

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


# ---------------------------------------------------------------------------
# Task 4: JSON API endpoints
# ---------------------------------------------------------------------------


@pytest.fixture
def templates_mock():
    from fastapi.templating import Jinja2Templates

    mock = MagicMock(spec=Jinja2Templates)
    with patch("app.api.events.templates", mock):
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
            id=1,
            name="Gottesdienst",
            start_date="2026-03-22T09:00:00Z",
            end_date="2026-03-22T11:00:00Z",
            calendar_name="GD",
            services=[EventService(service_id=1, name="Predigt", person_name="Max", is_accepted=True)],
        )
    ]

    response = await api_events(
        request=request,
        client=client,
        start_date="2026-03-22",
        end_date="2026-03-29",
        calendar_ids=["5"],
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
        request=request,
        client=client,
        start_date="2026-03-22",
        end_date="2026-03-29",
        calendar_ids=["5"],
    )

    assert response.status_code == 401


@pytest.mark.asyncio
@patch("app.api.events.fetch_agenda")
async def test_api_event_agenda_success(mock_fetch, config_mock):
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "token"
    client = AsyncMock()

    mock_fetch.return_value = [
        AgendaItem(
            position=1,
            type="default",
            title="Begruessung",
            start="2026-03-22T09:00:00Z",
            duration_seconds=300,
            responsible_names=["Max"],
            is_before_event=False,
        ),
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


# ---------------------------------------------------------------------------
# Task 9: PDF export routes
# ---------------------------------------------------------------------------


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
        AgendaItem(
            position=1,
            type="default",
            title="Begruessung",
            start="2026-03-22T09:00:00Z",
            duration_seconds=300,
            responsible_names=["Max"],
            is_before_event=False,
        ),
    ]
    mock_create_pdf.return_value = b"%PDF-1.4 fake"

    response = await api_agenda_pdf(
        request=request,
        event_id=1,
        event_name="Gottesdienst",
        event_start="2026-03-22T09:00:00Z",
        client=client,
    )

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "application/pdf"


@pytest.mark.asyncio
@patch("app.api.events.create_services_pdf")
@patch("app.api.events.fetch_events")
async def test_api_event_services_pdf(mock_fetch_events, mock_create_pdf, config_mock):
    from fastapi import Request
    from fastapi.responses import StreamingResponse

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "token"
    client = AsyncMock()

    mock_fetch_events.return_value = [
        EventSummary(
            id=1,
            name="GD",
            start_date="2026-03-22T09:00:00Z",
            end_date="2026-03-22T11:00:00Z",
            calendar_name="GD",
            services=[],
        ),
    ]
    mock_create_pdf.return_value = b"%PDF-1.4 fake"

    response = await api_event_services_pdf(
        request=request,
        event_id=1,
        event_name="GD",
        event_start="2026-03-22T09:00:00Z",
        client=client,
        start_date="2026-03-22",
        end_date="2026-03-29",
        calendar_ids=["5"],
    )

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "application/pdf"
