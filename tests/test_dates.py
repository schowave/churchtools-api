import unittest
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.dates import (
    MAX_RANGE_DAYS,
    export_timestamp,
    get_date_range_from_form,
    parse_iso_datetime,
    validate_date_range,
)


class TestDates(unittest.TestCase):
    def test_parse_iso_datetime_with_z(self):
        # Test parsing ISO datetime with Z suffix (UTC)
        dt_str = "2023-01-15T14:30:00Z"
        result = parse_iso_datetime(dt_str)

        # Check if result is timezone aware
        self.assertIsNotNone(result.tzinfo)

        # Check if conversion to Berlin timezone is correct (default)
        berlin_tz = ZoneInfo("Europe/Berlin")
        self.assertEqual(str(result.tzinfo), str(berlin_tz))

        # In winter time Berlin is UTC+1
        self.assertEqual(result.hour, 15)  # 14 UTC = 15 Berlin (assuming standard time)

    def test_parse_iso_datetime_custom_timezone(self):
        dt_str = "2023-01-15T14:30:00Z"
        ny_tz = ZoneInfo("America/New_York")
        result = parse_iso_datetime(dt_str, tz=ny_tz)
        self.assertEqual(result.hour, 9)  # 14 UTC = 9 EST

    def test_get_date_range_from_form_with_values(self):
        # Test with provided values
        start_date = "2023-01-01"
        end_date = "2023-01-31"
        result_start, result_end = get_date_range_from_form(start_date, end_date)

        self.assertEqual(result_start, start_date)
        self.assertEqual(result_end, end_date)

    def test_get_date_range_from_form_without_values(self):
        # Test without provided values (should return next Sunday and Sunday after next)
        result_start, result_end = get_date_range_from_form()

        # Parse the returned dates
        start_date = datetime.strptime(result_start, "%Y-%m-%d")
        end_date = datetime.strptime(result_end, "%Y-%m-%d")

        # Check if end_date is 7 days after start_date
        self.assertEqual((end_date - start_date).days, 7)

        # Check if start_date is a Sunday (weekday 6)
        self.assertEqual(start_date.weekday(), 6)

        # Check if end_date is a Sunday (weekday 6)
        self.assertEqual(end_date.weekday(), 6)


def test_parse_iso_datetime_date_only_is_local_midnight(monkeypatch):
    # All-day appointments come as plain dates; they must stay on that local date,
    # independent of the server's system timezone.
    import time
    from zoneinfo import ZoneInfo

    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    try:
        berlin = ZoneInfo("Europe/Berlin")
        result = parse_iso_datetime("2026-09-27", tz=berlin)
    finally:
        monkeypatch.undo()
        time.tzset()
    assert (result.year, result.month, result.day, result.hour, result.minute) == (2026, 9, 27, 0, 0)
    assert result.tzinfo == berlin


def test_export_timestamp_uses_configured_timezone():
    utc_now = datetime(2026, 9, 27, 8, 0, 0, tzinfo=UTC)
    assert export_timestamp(utc_now, tz=ZoneInfo("Europe/Berlin")) == "2026-09-27-10-00-00"


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2026-01-01", "2027-01-03"),  # 367 days
        ("2026-02-01", "2026-01-31"),
        ("2026-01-01T00:00:00", "2026-01-31"),
        ("20260101", "2026-01-31"),
        ("", "2026-01-31"),
    ],
)
def test_validate_date_range_rejects(start, end):
    with pytest.raises(ValueError):
        validate_date_range(start, end)


def test_validate_date_range_accepts_up_to_max_days():
    assert MAX_RANGE_DAYS == 366
    validate_date_range("2026-01-01", "2027-01-02")
    validate_date_range("2026-09-27", "2026-09-27")
