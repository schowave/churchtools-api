from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo


def parse_iso_datetime(dt_str: str, tz: Optional[ZoneInfo] = None) -> datetime:
    """Converts an ISO datetime string to a timezone-aware datetime."""
    if tz is None:
        from app.config import settings

        tz = settings.timezone

    if dt_str.endswith("Z"):
        dt = datetime.fromisoformat(dt_str.rstrip("Z"))
        utc_dt = dt.replace(tzinfo=timezone.utc)
    else:
        utc_dt = datetime.fromisoformat(dt_str)

    return utc_dt.astimezone(tz)


def get_date_range_from_form(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Tuple[str, str]:
    """
    Calculates a date range based on the provided values or uses default values.
    """
    today = datetime.today()
    next_sunday = today + timedelta(days=(6 - today.weekday()) % 7)
    sunday_after_next = next_sunday + timedelta(weeks=1)

    if not start_date:
        start_date = next_sunday.strftime("%Y-%m-%d")
    if not end_date:
        end_date = sunday_after_next.strftime("%Y-%m-%d")

    return start_date, end_date


def normalize_newlines(text: str) -> str:
    """
    Normalizes line breaks in a text.
    Replaces all types of line breaks (\r\n, \r) with \n.
    Also removes special Unicode characters that may sometimes appear in text fields.
    """
    if text is None:
        return ""
    # First replace \r\n with \n
    text = text.replace("\r\n", "\n")
    # Then replace single \r with \n
    text = text.replace("\r", "\n")
    # Remove special Unicode characters that may sometimes appear in text fields
    text = text.replace("\u2028", "\n")  # Line Separator
    text = text.replace("\u2029", "\n")  # Paragraph Separator
    return text
