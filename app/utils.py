import sqlite3

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


def fetch_calendars(login_token):
    url = f'{Config.CHURCHTOOLS_BASE_URL}/api/calendars'
    headers = {'Authorization': f'Login {login_token}'}

    response = requests.get(url, headers=headers)

    if response.ok:
        all_calendars = response.json().get('data', [])
        public_calendars = [calendar for calendar in all_calendars if calendar.get('isPublic') is True]
        return public_calendars
    else:
        response.raise_for_status()


def fetch_appointments(login_token, start_date, end_date, calendar_ids):
    berlin_tz = pytz.timezone('Europe/Berlin')
    start_date_datetime = berlin_tz.localize(datetime.strptime(start_date, '%Y-%m-%d'))
    end_date_datetime = berlin_tz.localize(datetime.strptime(end_date, '%Y-%m-%d'))

    headers = {'Authorization': f'Login {login_token}'}
    query_params = {
        'from': (start_date_datetime.strftime('%Y-%m-%d')),
        'to': (end_date_datetime.strftime('%Y-%m-%d'))
    }
    appointments = []
    seen_ids = set()  # Set to track seen appointment IDs

    for calendar_id in calendar_ids:
        url = f'{Config.CHURCHTOOLS_BASE_URL}/api/calendars/{calendar_id}/appointments'
        response = requests.get(url, headers=headers, params=query_params)
        if response.ok:
            appointment_counts = {}  # Dictionary to keep track of appointment counts

            for appointment in response.json()['data']:
                base_id = str(appointment['base']['id'])
                appointment_id = str(calendar_id) + "_" + base_id

                # Check if the appointment_id already exists, and increment the count
                if appointment_id in appointment_counts:
                    appointment_counts[appointment_id] += 1
                    appointment_id += f"_{appointment_counts[appointment_id]}"
                else:
                    appointment_counts[appointment_id] = 0  # Initialize count for new ID

                if appointment_id not in seen_ids:
                    seen_ids.add(appointment_id)
                    appointment['base']['id'] = appointment_id
                    appointments.append(appointment)

    appointments.sort(key=lambda x: parse_iso_datetime(x['calculated']['startDate']))
    return appointments


def get_date_range_from_form():
    today = datetime.today()
    next_sunday = today + timedelta(days=(6 - today.weekday()) % 7)
    sunday_after_next = next_sunday + timedelta(weeks=1)
    start_date = request.form.get('start_date', next_sunday.strftime('%Y-%m-%d'))
    end_date = request.form.get('end_date', sunday_after_next.strftime('%Y-%m-%d'))
    return start_date, end_date


def normalize_newlines(text):
    return text.replace('\r\n', '\n')


def save_additional_infos(appointment_info_list):
    try:
        with sqlite3.connect(Config.DB_PATH) as conn:
            cursor = conn.cursor()
            sql = '''INSERT OR REPLACE INTO appointments (id, additional_info) VALUES (?, ?)'''
            cursor.executemany(sql, appointment_info_list)
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def get_additional_infos(appointment_ids):
    try:
        with sqlite3.connect(Config.DB_PATH) as conn:
            cursor = conn.cursor()
            # Use SQL's "IN" clause to fetch multiple records at once
            placeholders = ','.join('?' for _ in appointment_ids)
            sql = f'SELECT id, additional_info FROM appointments WHERE id IN ({placeholders})'
            cursor.execute(sql, appointment_ids)
            results = cursor.fetchall()
            # Convert list of tuples into a dictionary
            info_dict = {id: info for id, info in results}
            return info_dict
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return {}


def save_color_settings(settings):
    db_path = Config.DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    sql = '''
    INSERT INTO color_settings (setting_name, background_color, background_alpha, date_color, description_color)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(setting_name) DO UPDATE SET 
        background_color = excluded.background_color,
        background_alpha = excluded.background_alpha,
        date_color = excluded.date_color,
        description_color = excluded.description_color
    '''
    try:
        cursor.execute(sql, (
            settings['name'], settings['background_color'], settings['background_alpha'], settings['date_color'],
            settings['description_color']))
        conn.commit()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()


def load_color_settings(setting_name):
    db_path = Config.DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # SQL query to load the settings
    sql = 'SELECT * FROM color_settings WHERE setting_name = ?'
    try:
        cursor.execute(sql, (setting_name,))
        data = cursor.fetchone()

        # Define the keys for the settings object
        keys = ['name', 'background_color', 'background_alpha', 'date_color', 'description_color']

        # If data is found, return it as a dictionary
        if data:
            return dict(zip(keys, data))

        # Default settings to return if no data is found
        default_settings = {
            'name': setting_name,
            'background_color': '#ffffff',
            'background_alpha': 128,
            'date_color': '#c1540c',
            'description_color': '#4e4e4e'
        }
        return default_settings

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        # Return default settings in case of an error
        return default_settings
    finally:
        conn.close()


def appointment_to_dict(appointment):
    start_date_from_appointment = appointment['calculated']['startDate']
    start_date_datetime = parse_iso_datetime(start_date_from_appointment)

    end_date_from_appointment = appointment['calculated']['endDate']
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
        'endDate': appointment['calculated']['endDate'],
        'address': appointment['base'].get('address', ''),
        'meetingAt': meeting_at,
        'information': appointment['base']['information'],
        'startDateView': start_date_datetime.strftime('%d.%m.%Y'),
        'startTimeView': start_date_datetime.strftime('%H:%M'),
        'endTimeView': end_date_datetime.strftime('%H:%M'),
        'additional_info': ""
    }
