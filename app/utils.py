import pytz
from datetime import datetime, timedelta
from fastapi import Request
from typing import Tuple, Dict, List, Any, Optional

def get_login_token(request: Request) -> Optional[str]:
    """
    Extrahiert das Login-Token aus den Cookies der Anfrage.
    """
    return request.cookies.get('login_token')

def parse_iso_datetime(dt_str: str) -> datetime:
    """
    Konvertiert einen ISO-Datetime-String in ein timezone-aware datetime-Objekt in der Europe/Berlin-Zeitzone.
    """
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

def get_date_range_from_form(start_date: str = None, end_date: str = None) -> Tuple[str, str]:
    """
    Berechnet einen Datumsbereich basierend auf den übergebenen Werten oder verwendet Standardwerte.
    """
    today = datetime.today()
    next_sunday = today + timedelta(days=(6 - today.weekday()) % 7)
    sunday_after_next = next_sunday + timedelta(weeks=1)
    
    if not start_date:
        start_date = next_sunday.strftime('%Y-%m-%d')
    if not end_date:
        end_date = sunday_after_next.strftime('%Y-%m-%d')
        
    return start_date, end_date

def normalize_newlines(text: str) -> str:
    """
    Normalisiert Zeilenumbrüche in einem Text.
    Ersetzt alle Arten von Zeilenumbrüchen (\r\n, \r) durch \n.
    Entfernt auch spezielle Unicode-Zeichen, die manchmal in Textfeldern erscheinen können.
    """
    if text is None:
        return ""
    # Zuerst \r\n durch \n ersetzen
    text = text.replace('\r\n', '\n')
    # Dann einzelne \r durch \n ersetzen
    text = text.replace('\r', '\n')
    # Remove special Unicode characters that may sometimes appear in text fields
    text = text.replace('\u2028', '\n')  # Line Separator
    text = text.replace('\u2029', '\n')  # Paragraph Separator
    return text
