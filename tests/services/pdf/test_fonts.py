import unittest
from unittest.mock import patch

from reportlab.pdfbase import pdfmetrics


class TestFontRegistration(unittest.TestCase):
    """Test font registration and caching."""

    def test_font_registration_is_cached(self):
        import app.services.pdf.fonts as fonts

        fonts._cached_fonts = None
        result1 = fonts.register_fonts()
        result2 = fonts.register_fonts()
        self.assertEqual(result1, result2)
        self.assertIsNotNone(fonts._cached_fonts)

    def test_font_fallback_on_missing_font(self):
        import app.services.pdf.fonts as fonts

        fonts._cached_fonts = None
        with patch.object(pdfmetrics, "getRegisteredFontNames", return_value=[]):
            with patch("app.services.pdf.fonts.TTFont", side_effect=Exception("Font not found")):
                font_name, bold_name = fonts.register_fonts()
                self.assertEqual(font_name, "Helvetica")

        fonts._cached_fonts = None
