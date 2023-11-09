import requests
import pytz
from datetime import datetime, timedelta
from flask import request
from dateutil.parser import parse

from config import Config


def get_login_token():
    return request.cookies.get('login_token')


def parse_iso_datetime(dt_str):
    # Create a timezone-aware datetime object in UTC if the string ends with 'Z'
    if dt_str.endswith('Z'):
        dt = datetime.fromisoformat(dt_str.rstrip('Z'))
        utc_dt = dt.replace(tzinfo=pytz.utc)
    else:
        # If the string does not end with 'Z', parse it as is
        utc_dt = datetime.fromisoformat(dt_str)

    # Convert the timezone from UTC to Europe/Berlin
    berlin_tz = pytz.timezone('Europe/Berlin')
    berlin_dt = utc_dt.astimezone(berlin_tz)
    return berlin_dt


def make_login_request(username, password):
    data = {"password": password, "rememberMe": True, "username": username}
    return requests.post(f'{Config.CHURCHTOOLS_BASE_URL}/api/login', json=data)


def fetch_appointments(login_token, start_date, end_date):
    berlin_tz = pytz.timezone('Europe/Berlin')
    start_date_datetime = berlin_tz.localize(datetime.strptime(start_date, '%Y-%m-%d'))
    end_date_datetime = berlin_tz.localize(datetime.strptime(end_date, '%Y-%m-%d'))
    end_date_replace = end_date_datetime.replace(hour=23, minute=59, second=59)

    headers = {'Authorization': f'Login {login_token}'}
    appointments = []
    seen_ids = set()  # Set to track seen appointment IDs

    for calendar_id in [47, 1, 2]:
        url = f'{Config.CHURCHTOOLS_BASE_URL}/api/calendars/{calendar_id}/appointments'
        response = requests.get(url, headers=headers)
        if response.ok:
            for appointment in response.json()['data']:
                appointment_id = appointment['base']['id']
                appointment_start_date = appointment['base']['startDate']
                # Combine the checks for seen ID and date range into a single condition
                if appointment_id not in seen_ids and start_date_datetime <= parse_iso_datetime(
                        appointment_start_date) <= end_date_replace:
                    seen_ids.add(appointment_id)
                    appointments.append(appointment)

    appointments.sort(key=lambda x: parse(x['base']['startDate']))
    return appointments


def get_date_range_from_form():
    today = datetime.today()
    next_sunday = today + timedelta(days=(6 - today.weekday()) % 7)
    sunday_after_next = next_sunday + timedelta(weeks=1)
    start_date = request.form.get('start_date', next_sunday.strftime('%Y-%m-%d'))
    end_date = request.form.get('end_date', sunday_after_next.strftime('%Y-%m-%d'))
    return start_date, end_date


def appointment_to_dict(appointment):
    start_date_from_appointment = appointment['base']['startDate']
    start_date_datetime = parse_iso_datetime(start_date_from_appointment)

    end_date_from_appointment = appointment['base']['endDate']
    end_date_datetime = parse_iso_datetime(end_date_from_appointment)

    address = appointment['base'].get('address', '')

    if address is not None:
        meeting_at = address.get('meetingAt', '')
    else:
        meeting_at = ''  # Or however you'd like to handle a missing address

    return {
        'id': appointment['base']['id'],
        'description': appointment['base']['caption'],
        'startDate': start_date_from_appointment,
        'endDate': appointment['base']['endDate'],
        'address': appointment['base'].get('address', ''),
        'meetingAt': meeting_at,
        'information': appointment['base']['information'],
        'startDateView': start_date_datetime.strftime('%d.%m.%Y'),
        'startTimeView': start_date_datetime.strftime('%H:%M'),
        'endTimeView': end_date_datetime.strftime('%H:%M')
    }
