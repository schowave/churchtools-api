from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

# Longest date range a request may ask for; bounds the ChurchTools responses and the size of exports
MAX_RANGE_DAYS = 366


def validate_date_range(start_date: str, end_date: str) -> None:
    """Raise ValueError unless both are ISO dates (YYYY-MM-DD) spanning at most MAX_RANGE_DAYS."""
    try:
        # strptime, not date.fromisoformat: the strings go to ChurchTools as-is, which expects exactly this format
        start, end = (datetime.strptime(value, "%Y-%m-%d").date() for value in (start_date, end_date))
    except ValueError:
        raise ValueError("Ungültiges Datum (erwartet JJJJ-MM-TT)") from None
    if end < start:
        raise ValueError("Das Enddatum liegt vor dem Startdatum")
    if (end - start).days > MAX_RANGE_DAYS:
        raise ValueError(f"Der Zeitraum darf höchstens {MAX_RANGE_DAYS} Tage umfassen")


def parse_iso_datetime(dt_str: str, tz: ZoneInfo | None = None) -> datetime:
    """Converts an ISO datetime string to a timezone-aware datetime."""
    if tz is None:
        from app.config import settings

        tz = settings.timezone

    if dt_str.endswith("Z"):
        dt = datetime.fromisoformat(dt_str.rstrip("Z"))
        utc_dt = dt.replace(tzinfo=UTC)
    else:
        utc_dt = datetime.fromisoformat(dt_str)

    if utc_dt.tzinfo is None:
        # Values without offset (e.g. all-day dates like "2026-09-27") are local to the
        # configured timezone; astimezone() would read them in the server's system timezone.
        return utc_dt.replace(tzinfo=tz)
    return utc_dt.astimezone(tz)


def get_date_range_from_form(start_date: str | None = None, end_date: str | None = None) -> tuple[str, str]:
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


def export_timestamp(now: datetime | None = None, tz: ZoneInfo | None = None) -> str:
    """Timestamp for export filenames in the configured timezone (the container runs in UTC)."""
    if tz is None:
        from app.config import settings

        tz = settings.timezone
    return (now or datetime.now(tz)).astimezone(tz).strftime("%Y-%m-%d-%H-%M-%S")
