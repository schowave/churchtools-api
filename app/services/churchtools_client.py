import asyncio
from datetime import datetime, timedelta
from typing import List

import httpx
import structlog

from app.config import settings
from app.schemas import AgendaItem, AppointmentData, EventService, EventSummary
from app.utils import parse_iso_datetime

logger = structlog.get_logger()


class AuthenticationError(Exception):
    """Raised when the ChurchTools API rejects the login token (401/403)."""


def _auth_headers(login_token: str) -> dict:
    return {"Authorization": f"Login {login_token}"}


def _extract_appointment(item: dict) -> dict:
    """Extract appointment data, handling both API response formats.

    The OpenAPI spec documents data[].appointment.base but the actual API
    returns data[].base directly. This handles both variants defensively.
    """
    if "appointment" in item:
        return item["appointment"]
    return item


async def fetch_calendars(login_token: str, client: httpx.AsyncClient):
    url = f"{settings.churchtools_base_url}/api/calendars"

    response = await client.get(url, headers=_auth_headers(login_token))

    if response.status_code in (401, 403):
        raise AuthenticationError("Login token is invalid or expired")

    if response.status_code == 200:
        all_calendars = response.json().get("data", [])
        # isPublic is deprecated in the API but no replacement is documented yet.
        # We keep using it until ChurchTools provides a documented alternative.
        public_calendars = [calendar for calendar in all_calendars if calendar.get("isPublic") is True]
        return public_calendars
    else:
        response.raise_for_status()


async def _fetch_calendar_appointments(
    client: httpx.AsyncClient, calendar_id: int, headers: dict, query_params: dict
) -> list[tuple[int, dict]]:
    """Fetch appointments for a single calendar. Returns list of (calendar_id, appointment_dict) tuples."""
    url = f"{settings.churchtools_base_url}/api/calendars/{calendar_id}/appointments"
    response = await client.get(url, headers=headers, params=query_params)

    if response.status_code in (401, 403):
        raise AuthenticationError("Login token is invalid or expired")

    if response.status_code != 200:
        logger.warning(f"Failed to fetch appointments for calendar {calendar_id}: HTTP {response.status_code}")
        return []

    return [(calendar_id, _extract_appointment(item)) for item in response.json()["data"]]


async def fetch_appointments(
    login_token: str, start_date: str, end_date: str, calendar_ids: List[int], client: httpx.AsyncClient
):
    headers = _auth_headers(login_token)
    query_params = {
        "from": start_date,
        "to": end_date,
    }
    appointments = []
    seen_ids = set()

    # Fetch all calendars in parallel
    tasks = [_fetch_calendar_appointments(client, cal_id, headers, query_params) for cal_id in calendar_ids]
    results = await asyncio.gather(*tasks)

    for calendar_results in results:
        appointment_counts = {}

        for calendar_id, appointment in calendar_results:
            base_id = str(appointment["base"]["id"])
            appointment_id = str(calendar_id) + "_" + base_id

            if appointment_id in appointment_counts:
                appointment_counts[appointment_id] += 1
                appointment_id += f"_{appointment_counts[appointment_id]}"
            else:
                appointment_counts[appointment_id] = 0

            if appointment_id not in seen_ids:
                seen_ids.add(appointment_id)
                appointment["base"]["id"] = appointment_id
                appointments.append(appointment)

    appointments.sort(key=lambda x: parse_iso_datetime(x["calculated"]["startDate"]))
    return appointments


def parse_appointment(raw: dict) -> AppointmentData:
    """Convert a raw API appointment dict to a structured AppointmentData model."""
    address = raw["base"].get("address") or {}
    # meetingAt is undocumented in the OpenAPI spec; fall back to address name
    meeting_at = address.get("meetingAt") or address.get("name") or ""

    return AppointmentData(
        id=str(raw["base"]["id"]),
        # Prefer "title" (current API field) with fallback to deprecated "caption"
        title=raw["base"].get("title") or raw["base"].get("caption", ""),
        start_date=raw["calculated"]["startDate"],
        end_date=raw["calculated"]["endDate"],
        meeting_at=meeting_at,
        # API field "description" replaces deprecated "information"
        information=raw["base"].get("description") or raw["base"].get("information") or "",
    )


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
                    name=svc.get("name") or "",
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

        responsible_names = []
        responsible = raw_item.get("responsible", {})
        for entry in responsible.get("persons", []):
            name = _extract_person_name(entry.get("person"))
            if name:
                responsible_names.append(name)

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
