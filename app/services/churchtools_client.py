import asyncio
import logging
from typing import List

import httpx

from app.config import Config
from app.schemas import AppointmentData
from app.utils import parse_iso_datetime

logger = logging.getLogger(__name__)


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


async def fetch_calendars(login_token: str):
    url = f"{Config.CHURCHTOOLS_BASE_URL}/api/calendars"

    async with httpx.AsyncClient() as client:
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
    url = f"{Config.CHURCHTOOLS_BASE_URL}/api/calendars/{calendar_id}/appointments"
    response = await client.get(url, headers=headers, params=query_params)

    if response.status_code in (401, 403):
        raise AuthenticationError("Login token is invalid or expired")

    if response.status_code != 200:
        logger.warning(f"Failed to fetch appointments for calendar {calendar_id}: HTTP {response.status_code}")
        return []

    return [(calendar_id, _extract_appointment(item)) for item in response.json()["data"]]


async def fetch_appointments(login_token: str, start_date: str, end_date: str, calendar_ids: List[int]):
    headers = _auth_headers(login_token)
    query_params = {
        "from": start_date,
        "to": end_date,
    }
    appointments = []
    seen_ids = set()

    async with httpx.AsyncClient() as client:
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
