import asyncio
from datetime import datetime, timedelta

import httpx2
import structlog

from app.config import settings
from app.dates import parse_iso_datetime
from app.schemas import AgendaItem, AppointmentData, CurrentUser, EventService, EventSummary

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


async def fetch_current_user(login_token: str, client: httpx2.AsyncClient) -> CurrentUser:
    """Fetch the person the login token belongs to."""
    response = await client.get(f"{settings.churchtools_base_url}/api/whoami", headers=_auth_headers(login_token))
    if response.status_code in (401, 403):
        raise AuthenticationError("Login token is invalid or expired")
    response.raise_for_status()

    data = response.json().get("data", {})
    return CurrentUser(
        id=data["id"],
        first_name=data.get("firstName") or "",
        last_name=data.get("lastName") or "",
        email=data.get("email") or "",
    )


async def fetch_person_group_ids(login_token: str, person_id: int, client: httpx2.AsyncClient) -> set[int]:
    """Ids of the groups a person is an active member of. Empty if ChurchTools refuses the lookup."""
    url = f"{settings.churchtools_base_url}/api/persons/{person_id}/groups"
    response = await client.get(url, headers=_auth_headers(login_token))
    if response.status_code != 200:
        logger.warning("fetch_person_groups_failed", status=response.status_code)
        return set()

    group_ids = set()
    for membership in response.json().get("data", []):
        if membership.get("groupMemberStatus", "active") != "active":
            continue  # e.g. a pending membership request
        group = membership.get("group") or {}
        group_id = group.get("domainIdentifier") or group.get("id") or membership.get("groupId")
        if group_id is not None and str(group_id).isdigit():
            group_ids.add(int(group_id))
    return group_ids


async def fetch_calendars(login_token: str, client: httpx2.AsyncClient):
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
    client: httpx2.AsyncClient, calendar_id: int, headers: dict, query_params: dict
) -> list[tuple[int, dict]]:
    """Fetch appointments for a single calendar. Returns list of (calendar_id, appointment_dict) tuples."""
    url = f"{settings.churchtools_base_url}/api/calendars/{calendar_id}/appointments"
    response = await client.get(url, headers=headers, params=query_params)

    if response.status_code in (401, 403):
        raise AuthenticationError("Login token is invalid or expired")

    if response.status_code != 200:
        logger.warning("fetch_appointments_failed", calendar_id=calendar_id, status=response.status_code)
        return []

    return [(calendar_id, _extract_appointment(item)) for item in response.json()["data"]]


async def fetch_appointments(
    login_token: str, start_date: str, end_date: str, calendar_ids: list[int], client: httpx2.AsyncClient
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
        for calendar_id, appointment in calendar_results:
            # Occurrences of a series share base.id; the start date tells them apart. The id must not
            # depend on the requested date range, since custom texts are stored under it.
            start_date = appointment["calculated"]["startDate"]
            appointment_id = f"{calendar_id}_{appointment['base']['id']}_{start_date}"
            if appointment_id not in seen_ids:
                seen_ids.add(appointment_id)
                appointment["base"]["id"] = appointment_id
                appointments.append(appointment)

    appointments.sort(key=lambda x: parse_iso_datetime(x["calculated"]["startDate"]))
    return appointments


def legacy_appointment_ids(appointment_ids: list[str]) -> dict[str, str]:
    """Map current appointment ids to the ids used before v7.1, for migrating stored custom texts.

    Old ids were "{calendar}_{base}" for the first occurrence of a series in the loaded range and
    "{calendar}_{base}_{n}" for the n-th one after it. Recomputing them for the current range yields
    the occurrence the old version showed the text on.
    """
    occurrences: dict[str, list[tuple[datetime, str]]] = {}
    for appointment_id in appointment_ids:
        calendar_id, base_id, start_date = appointment_id.split("_", 2)
        occurrences.setdefault(f"{calendar_id}_{base_id}", []).append((parse_iso_datetime(start_date), appointment_id))

    legacy_ids = {}
    for series_id, entries in occurrences.items():
        for index, (_, appointment_id) in enumerate(sorted(entries)):
            legacy_ids[appointment_id] = series_id if index == 0 else f"{series_id}_{index}"
    return legacy_ids


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
        all_day=bool(raw["base"].get("allDay", False)),
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


async def _fetch_service_names(login_token: str, client: httpx2.AsyncClient) -> dict[int, str]:
    """Fetch service definitions and return a {serviceId: name} lookup."""
    url = f"{settings.churchtools_base_url}/api/services"
    response = await client.get(url, headers=_auth_headers(login_token))
    if response.status_code in (401, 403):
        raise AuthenticationError("Login token is invalid or expired")
    if response.status_code != 200:
        logger.warning("fetch_services_failed", status=response.status_code)
        return {}
    return {svc["id"]: svc.get("name", "") for svc in response.json().get("data", [])}


async def fetch_events(
    login_token: str,
    start_date: str,
    end_date: str,
    calendar_ids: list[str],
    client: httpx2.AsyncClient,
) -> list[EventSummary]:
    """Fetch events from ChurchTools, filtered by calendar IDs. Canceled events are excluded."""
    # Fetch events and service name lookup in parallel
    events_url = f"{settings.churchtools_base_url}/api/events"
    to_date = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    params = {"from": start_date, "to": to_date, "include": "eventServices"}

    events_response, service_names = await asyncio.gather(
        client.get(events_url, headers=_auth_headers(login_token), params=params),
        _fetch_service_names(login_token, client),
    )

    if events_response.status_code in (401, 403):
        raise AuthenticationError("Login token is invalid or expired")
    events_response.raise_for_status()

    calendar_ids_set = set(calendar_ids)
    events = []
    for item in events_response.json().get("data", []):
        if item.get("isCanceled", False):
            continue
        cal = item.get("calendar", {})
        if cal.get("domainIdentifier") not in calendar_ids_set:
            continue

        services = []
        for svc in item.get("eventServices", []):
            service_id = svc.get("serviceId", svc.get("id", 0))
            services.append(
                EventService(
                    service_id=service_id,
                    name=service_names.get(service_id, ""),
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


async def fetch_event(login_token: str, event_id: int, client: httpx2.AsyncClient) -> EventSummary | None:
    """Fetch a single event's basic data (without services). Returns None if it does not exist."""
    url = f"{settings.churchtools_base_url}/api/events/{event_id}"
    response = await client.get(url, headers=_auth_headers(login_token))
    if response.status_code == 404:
        return None
    if response.status_code in (401, 403):
        raise AuthenticationError("Login token is invalid or expired")
    response.raise_for_status()

    data = response.json().get("data", {})
    return EventSummary(
        id=data["id"],
        name=data.get("name", ""),
        start_date=data.get("startDate", ""),
        end_date=data.get("endDate", ""),
        calendar_name=(data.get("calendar") or {}).get("title", ""),
    )


async def fetch_agenda(
    login_token: str,
    event_id: int,
    client: httpx2.AsyncClient,
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
