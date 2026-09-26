import unittest

from app.text import normalize_newlines


class TestText(unittest.TestCase):
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
