import unittest
from datetime import datetime
import pytz
from app.utils import parse_iso_datetime, normalize_newlines, get_date_range_from_form

class TestUtils(unittest.TestCase):
    def test_parse_iso_datetime_with_z(self):
        # Test parsing ISO datetime with Z suffix (UTC)
        dt_str = "2023-01-15T14:30:00Z"
        result = parse_iso_datetime(dt_str)
        
        # Check if result is timezone aware
        self.assertIsNotNone(result.tzinfo)
        
        # Check if conversion to Berlin timezone is correct
        berlin_tz = pytz.timezone('Europe/Berlin')
        # We only check if it's the same timezone, not the exact tzinfo object
        self.assertEqual(str(result.tzinfo), str(berlin_tz))
        
        # In winter time Berlin is UTC+1
        self.assertEqual(result.hour, 15)  # 14 UTC = 15 Berlin (assuming standard time)
    
    def test_normalize_newlines(self):
        # Test with Windows-style line endings
        windows_text = "Line1\r\nLine2\r\nLine3"
        expected = "Line1\nLine2\nLine3"
        self.assertEqual(normalize_newlines(windows_text), expected)
        
        # Test with Mac-style line endings
        mac_text = "Line1\rLine2\rLine3"
        self.assertEqual(normalize_newlines(mac_text), expected)
        
        # Test with mixed line endings
        mixed_text = "Line1\r\nLine2\rLine3\nLine4"
        expected_mixed = "Line1\nLine2\nLine3\nLine4"
        self.assertEqual(normalize_newlines(mixed_text), expected_mixed)
        
        # Test with Unicode line separators
        unicode_text = "Line1\u2028Line2\u2029Line3"
        expected_unicode = "Line1\nLine2\nLine3"
        self.assertEqual(normalize_newlines(unicode_text), expected_unicode)
        
        # Test with None input
        self.assertEqual(normalize_newlines(None), "")
    
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
        start_date = datetime.strptime(result_start, '%Y-%m-%d')
        end_date = datetime.strptime(result_end, '%Y-%m-%d')
        
        # Check if end_date is 7 days after start_date
        self.assertEqual((end_date - start_date).days, 7)
        
        # Check if start_date is a Sunday (weekday 6)
        self.assertEqual(start_date.weekday(), 6)
        
        # Check if end_date is a Sunday (weekday 6)
        self.assertEqual(end_date.weekday(), 6)

if __name__ == '__main__':
    unittest.main()