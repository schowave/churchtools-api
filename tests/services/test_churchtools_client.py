from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas import AppointmentData
from app.services.churchtools_client import (
    AuthenticationError,
    _extract_person_name,
    fetch_agenda,
    fetch_appointments,
    fetch_calendars,
    fetch_events,
    legacy_appointment_ids,
    parse_appointment,
)


@pytest.mark.asyncio
async def test_fetch_calendars_success(config_mock):
    # Mock httpx client
    client = AsyncMock()

    # Mock successful response
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "data": [
            {"id": 1, "name": "Calendar 1", "isPublic": True},
            {"id": 2, "name": "Calendar 2", "isPublic": False},
            {"id": 3, "name": "Calendar 3", "isPublic": True},
        ]
    }
    client.get.return_value = response

    # Call the function
    result = await fetch_calendars("test_token", client)

    # Check that client.get was called with correct parameters
    client.get.assert_called_once_with(
        f"{config_mock['CHURCHTOOLS_BASE_URL']}/api/calendars", headers={"Authorization": "Login test_token"}
    )

    # Check that only public calendars were returned
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 3


@pytest.mark.asyncio
async def test_fetch_calendars_auth_error():
    # Mock httpx client
    client = AsyncMock()

    # Mock 401 response
    response = MagicMock()
    response.status_code = 401
    client.get.return_value = response

    # Call the function and check that it raises AuthenticationError
    with pytest.raises(AuthenticationError):
        await fetch_calendars("invalid_token", client)


@pytest.mark.asyncio
async def test_fetch_appointments(config_mock):
    # Mock httpx client
    client = AsyncMock()

    # Mock successful responses for two calendars
    response1 = MagicMock()
    response1.status_code = 200
    response1.json.return_value = {
        "data": [
            {
                "base": {
                    "id": "101",
                    "caption": "Event 1",
                    "information": "Info 1",
                    "address": {"meetingAt": "Location 1"},
                },
                "calculated": {"startDate": "2023-01-15T10:00:00Z", "endDate": "2023-01-15T12:00:00Z"},
            }
        ]
    }

    response2 = MagicMock()
    response2.status_code = 200
    response2.json.return_value = {
        "data": [
            {
                "base": {
                    "id": "102",
                    "caption": "Event 2",
                    "information": "Info 2",
                    "address": {"meetingAt": "Location 2"},
                },
                "calculated": {"startDate": "2023-01-16T14:00:00Z", "endDate": "2023-01-16T16:00:00Z"},
            }
        ]
    }

    # Set up client to return different responses for different calendar IDs
    client.get.side_effect = [response1, response2]

    # Call the function
    result = await fetch_appointments("test_token", "2023-01-15", "2023-01-16", [1, 2], client)

    # Check that client.get was called twice with correct parameters
    assert client.get.call_count == 2
    client.get.assert_any_call(
        f"{config_mock['CHURCHTOOLS_BASE_URL']}/api/calendars/1/appointments",
        headers={"Authorization": "Login test_token"},
        params={"from": "2023-01-15", "to": "2023-01-16"},
    )
    client.get.assert_any_call(
        f"{config_mock['CHURCHTOOLS_BASE_URL']}/api/calendars/2/appointments",
        headers={"Authorization": "Login test_token"},
        params={"from": "2023-01-15", "to": "2023-01-16"},
    )

    # Check that appointments were returned and IDs were modified
    assert len(result) == 2
    assert result[0]["base"]["id"] == "1_101_2023-01-15T10:00:00Z"
    assert result[1]["base"]["id"] == "2_102_2023-01-16T14:00:00Z"


def test_parse_appointment():
    # Test with deprecated fields (caption/information) - fallback path
    raw = {
        "base": {
            "id": "1_101",
            "caption": "Test Event",
            "information": "Test Info",
            "address": {"meetingAt": "Test Location"},
        },
        "calculated": {"startDate": "2023-01-15T10:00:00Z", "endDate": "2023-01-15T12:00:00Z"},
    }

    result = parse_appointment(raw)

    assert isinstance(result, AppointmentData)
    assert result.id == "1_101"
    assert result.title == "Test Event"
    assert result.start_date == "2023-01-15T10:00:00Z"
    assert result.end_date == "2023-01-15T12:00:00Z"
    assert result.information == "Test Info"
    assert result.meeting_at == "Test Location"
    assert result.start_date_view == "15.01.2023"
    assert result.start_time_view == "11:00"  # UTC+1 for Berlin
    assert result.end_time_view == "13:00"  # UTC+1 for Berlin
    assert result.additional_info == ""


def test_parse_appointment_with_new_fields():
    # Test with new API fields (title/description) - preferred path
    raw = {
        "base": {
            "id": "1_101",
            "title": "New Title",
            "caption": "Old Caption",
            "description": "New Description",
            "information": "Old Info",
            "address": {"name": "Church Hall"},
        },
        "calculated": {"startDate": "2023-01-15T10:00:00Z", "endDate": "2023-01-15T12:00:00Z"},
    }

    result = parse_appointment(raw)

    # Should prefer new fields over deprecated ones
    assert result.title == "New Title"
    assert result.information == "New Description"
    assert result.meeting_at == "Church Hall"


def test_parse_appointment_missing_address():
    raw = {
        "base": {"id": "1_102", "caption": "Test Event 2", "information": "Test Info 2", "address": None},
        "calculated": {"startDate": "2023-01-16T14:00:00Z", "endDate": "2023-01-16T16:00:00Z"},
    }

    result = parse_appointment(raw)

    assert result.meeting_at == ""


def test_parse_appointment_nested_format():
    # Test the OpenAPI spec format: data[].appointment.base
    raw = {
        "appointment": {
            "base": {
                "id": "1_103",
                "title": "Nested Event",
                "address": {},
            },
            "calculated": {"startDate": "2023-01-17T09:00:00Z", "endDate": "2023-01-17T10:00:00Z"},
        }
    }

    from app.services.churchtools_client import _extract_appointment

    extracted = _extract_appointment(raw)
    result = parse_appointment(extracted)

    assert result.id == "1_103"
    assert result.title == "Nested Event"


@pytest.mark.asyncio
async def test_fetch_appointments_deduplication(config_mock):
    """Same appointment appearing in multiple calendars should be deduplicated."""
    client = AsyncMock()

    def make_appointment():
        return {
            "base": {
                "id": "101",
                "title": "Shared Event",
                "address": {},
            },
            "calculated": {"startDate": "2023-01-15T10:00:00Z", "endDate": "2023-01-15T12:00:00Z"},
        }

    response1 = MagicMock()
    response1.status_code = 200
    response1.json.return_value = {"data": [make_appointment()]}

    response2 = MagicMock()
    response2.status_code = 200
    response2.json.return_value = {"data": [make_appointment()]}

    client.get.side_effect = [response1, response2]

    result = await fetch_appointments("token", "2023-01-15", "2023-01-16", [1, 2], client)

    # Same base ID in different calendars -> different composite IDs, both kept
    assert len(result) == 2
    ids = {r["base"]["id"] for r in result}
    assert "1_101_2023-01-15T10:00:00Z" in ids
    assert "2_101_2023-01-15T10:00:00Z" in ids


@pytest.mark.asyncio
async def test_fetch_appointments_partial_failure(config_mock):
    """If one calendar fails, appointments from other calendars should still be returned."""
    client = AsyncMock()

    success_response = MagicMock()
    success_response.status_code = 200
    success_response.json.return_value = {
        "data": [
            {
                "base": {"id": "101", "title": "Event 1", "address": {}},
                "calculated": {"startDate": "2023-01-15T10:00:00Z", "endDate": "2023-01-15T12:00:00Z"},
            }
        ]
    }

    fail_response = MagicMock()
    fail_response.status_code = 500

    client.get.side_effect = [success_response, fail_response]

    result = await fetch_appointments("token", "2023-01-15", "2023-01-16", [1, 2], client)

    assert len(result) == 1
    assert result[0]["base"]["id"] == "1_101_2023-01-15T10:00:00Z"


def test_parse_appointment_all_day():
    # ChurchTools marks all-day appointments with base.allDay and sends date-only values
    raw = {
        "base": {"id": "2_7", "title": "17. So. n. Trinitatis", "allDay": True},
        "calculated": {"startDate": "2026-09-27", "endDate": "2026-09-27"},
    }

    result = parse_appointment(raw)

    assert result.all_day is True
    assert result.start_date_view == "27.09.2026"


def test_parse_appointment_timed_is_not_all_day():
    raw = {
        "base": {"id": "2_8", "title": "Gottesdienst", "allDay": False},
        "calculated": {"startDate": "2026-09-27T08:00:00Z", "endDate": "2026-09-27T09:00:00Z"},
    }

    assert parse_appointment(raw).all_day is False


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


@pytest.mark.asyncio
async def test_fetch_event(config_mock):
    from app.services.churchtools_client import fetch_event

    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "data": {
            "id": 1275,
            "name": "GOTTESDIENST",
            "startDate": "2026-09-06T08:00:00Z",
            "endDate": "2026-09-06T09:30:00Z",
            "calendar": {"title": "GOTTESDIENSTE"},
        }
    }
    client.get.return_value = response

    event = await fetch_event("token", 1275, client)

    assert (event.id, event.name, event.start_date, event.calendar_name) == (
        1275,
        "GOTTESDIENST",
        "2026-09-06T08:00:00Z",
        "GOTTESDIENSTE",
    )
    assert client.get.call_args[0][0].endswith("/api/events/1275")


@pytest.mark.asyncio
async def test_fetch_appointments_series_ids_do_not_depend_on_date_range(config_mock):
    """Occurrences of a series keep their id when the date range changes, so custom texts stay attached."""

    def occurrence(start):
        return {
            "base": {"id": "101", "title": "Hauskreis", "address": {}},
            "calculated": {"startDate": start, "endDate": start},
        }

    def response(*starts):
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {"data": [occurrence(s) for s in starts]}
        return mock

    client = AsyncMock()
    client.get.side_effect = [
        response("2023-01-15T10:00:00Z", "2023-01-22T10:00:00Z"),
        response("2023-01-22T10:00:00Z"),
    ]

    wide = await fetch_appointments("token", "2023-01-15", "2023-01-22", [1], client)
    narrow = await fetch_appointments("token", "2023-01-20", "2023-01-22", [1], client)

    assert [a["base"]["id"] for a in wide] == ["1_101_2023-01-15T10:00:00Z", "1_101_2023-01-22T10:00:00Z"]
    assert narrow[0]["base"]["id"] == wide[1]["base"]["id"]


def test_legacy_appointment_ids_number_series_occurrences_by_date():
    ids = [
        "1_7_2026-10-11T08:00:00Z",
        "1_7_2026-10-04T08:00:00Z",
        "2_7_2026-10-04T08:00:00Z",
        "1_9_2026-10-05",
    ]

    assert legacy_appointment_ids(ids) == {
        "1_7_2026-10-04T08:00:00Z": "1_7",
        "1_7_2026-10-11T08:00:00Z": "1_7_1",
        "2_7_2026-10-04T08:00:00Z": "2_7",
        "1_9_2026-10-05": "1_9",
    }
