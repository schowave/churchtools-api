import logging
from typing import List

import httpx

from app.config import Config
from app.utils import parse_iso_datetime

logger = logging.getLogger(__name__)


def _auth_headers(login_token: str) -> dict:
    return {"Authorization": f"Login {login_token}"}


async def fetch_calendars(login_token: str):
    url = f"{Config.CHURCHTOOLS_BASE_URL}/api/calendars"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=_auth_headers(login_token))

        if response.status_code == 200:
            all_calendars = response.json().get("data", [])
            public_calendars = [calendar for calendar in all_calendars if calendar.get("isPublic") is True]
            return public_calendars
        else:
            response.raise_for_status()


async def fetch_appointments(login_token: str, start_date: str, end_date: str, calendar_ids: List[int]):
    headers = _auth_headers(login_token)
    query_params = {
        "from": start_date,
        "to": end_date,
    }
    appointments = []
    seen_ids = set()

    async with httpx.AsyncClient() as client:
        for calendar_id in calendar_ids:
            url = f"{Config.CHURCHTOOLS_BASE_URL}/api/calendars/{calendar_id}/appointments"
            response = await client.get(url, headers=headers, params=query_params)

            if response.status_code != 200:
                logger.warning(f"Failed to fetch appointments for calendar {calendar_id}: HTTP {response.status_code}")
                continue

            appointment_counts = {}

            for appointment in response.json()["data"]:
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


def appointment_to_dict(appointment):
    start_date_from_appointment = appointment["calculated"]["startDate"]
    start_date_datetime = parse_iso_datetime(start_date_from_appointment)

    end_date_from_appointment = appointment["calculated"]["endDate"]
    end_date_datetime = parse_iso_datetime(end_date_from_appointment)

    meeting_at = (appointment["base"].get("address") or {}).get("meetingAt", "")

    return {
        "id": appointment["base"]["id"],
        "description": appointment["base"]["caption"],
        "startDate": start_date_from_appointment,
        "endDate": appointment["calculated"]["endDate"],
        "address": appointment["base"].get("address", ""),
        "meetingAt": meeting_at,
        "information": appointment["base"]["information"],
        "startDateView": start_date_datetime.strftime("%d.%m.%Y"),
        "startTimeView": start_date_datetime.strftime("%H:%M"),
        "endTimeView": end_date_datetime.strftime("%H:%M"),
        "additional_info": "",
    }
