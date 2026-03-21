import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.config import settings
from app.schemas import AgendaItem, EventService, EventSummary
from app.services.churchtools_client import fetch_events, _extract_person_name


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
