import io
import os
import unittest
from unittest.mock import MagicMock, patch

from reportlab.lib.pagesizes import landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from app.services.pdf_generator import (
    create_pdf,
    create_transparent_image,
    draw_background_image,
    draw_transparent_rectangle,
    setup_new_page,
    wrap_text,
)


class TestPdfGenerator(unittest.TestCase):
    def setUp(self):
        # Mock Config
        self.config_mock = {"FILE_DIRECTORY": "/tmp/test_files"}
        self.config_patch = patch(
            "app.services.pdf_generator.Config", FILE_DIRECTORY=self.config_mock["FILE_DIRECTORY"]
        )
        self.config_patch.start()

        # Ensure test directory exists
        os.makedirs(self.config_mock["FILE_DIRECTORY"], exist_ok=True)

    def tearDown(self):
        self.config_patch.stop()

    @patch("app.services.pdf_generator.ImageReader")
    def test_draw_background_image(self, mock_image_reader):
        # Mock canvas and image
        canvas_mock = MagicMock(spec=canvas.Canvas)
        image_stream = io.BytesIO(b"test image data")

        # Mock ImageReader instance
        image_mock = MagicMock()
        image_mock.getSize.return_value = (800, 600)
        mock_image_reader.return_value = image_mock

        # Call the function
        draw_background_image(canvas_mock, image_stream, 1200, 675)

        # Check that ImageReader was called with the image stream
        mock_image_reader.assert_called_once_with(image_stream)

        # Check that drawImage was called with correct parameters
        canvas_mock.drawImage.assert_called_once()
        args = canvas_mock.drawImage.call_args[0]
        kwargs = canvas_mock.drawImage.call_args[1]

        self.assertEqual(args[0], image_mock)
        # We only check if the position is within a reasonable range
        self.assertTrue(100 <= args[1] <= 300)  # x position should be approximately centered
        self.assertTrue(0 <= args[2] <= 100)  # y position should be approximately centered
        # We don't check the exact values, just the ratio
        self.assertTrue(kwargs["width"] > 0)
        self.assertTrue(kwargs["height"] > 0)
        # Check that the aspect ratio is maintained
        self.assertAlmostEqual(kwargs["width"] / kwargs["height"], 800 / 600, places=1)
        self.assertEqual(kwargs["mask"], "auto")

    def test_draw_background_image_none(self):
        # Mock canvas
        canvas_mock = MagicMock(spec=canvas.Canvas)

        # Call the function with None image
        draw_background_image(canvas_mock, None, 1200, 675)

        # Check that drawImage was not called
        canvas_mock.drawImage.assert_not_called()

    @patch("app.services.pdf_generator.ImageReader")
    def test_draw_background_image_error(self, mock_image_reader):
        # Mock canvas and image
        canvas_mock = MagicMock(spec=canvas.Canvas)
        image_stream = io.BytesIO(b"test image data")

        # Mock ImageReader to raise an exception
        mock_image_reader.side_effect = Exception("Test error")

        # Call the function
        draw_background_image(canvas_mock, image_stream, 1200, 675)

        # Check that drawImage was not called
        canvas_mock.drawImage.assert_not_called()

    @patch("app.services.pdf_generator.Image")
    @patch("app.services.pdf_generator.ImageColor")
    def test_create_transparent_image(self, mock_image_color, mock_image):
        # Mock ImageColor.getcolor
        mock_image_color.getcolor.return_value = (255, 255, 255, 255)

        # Mock Image.new
        image_mock = MagicMock()
        mock_image.new.return_value = image_mock

        # Call the function
        result = create_transparent_image(800, 600, "#ffffff", 128)

        # Check that ImageColor.getcolor was called with correct parameters
        mock_image_color.getcolor.assert_called_once_with("#ffffff", "RGBA")

        # Check that Image.new was called with correct parameters
        mock_image.new.assert_called_once_with("RGBA", (800, 600), (255, 255, 255, 128))

        # Check that the result is the mocked image
        self.assertEqual(result, image_mock)

    @patch("app.services.pdf_generator.create_transparent_image")
    @patch("app.services.pdf_generator.ImageReader")
    def test_draw_transparent_rectangle(self, mock_image_reader, mock_create_image):
        # Mock canvas
        canvas_mock = MagicMock(spec=canvas.Canvas)

        # Mock create_transparent_image
        image_mock = MagicMock()
        mock_create_image.return_value = image_mock

        # Mock BytesIO
        mock_byte_io = MagicMock(spec=io.BytesIO)

        # Mock image save method
        def mock_save(stream, format):
            pass

        image_mock.save.side_effect = mock_save

        # Mock BytesIO constructor
        with patch("io.BytesIO", return_value=mock_byte_io):
            # Call the function
            draw_transparent_rectangle(canvas_mock, 100, 200, 300, 400, "#ffffff", 128)

            # Check that create_transparent_image was called with correct parameters
            mock_create_image.assert_called_once_with(300, 400, "#ffffff", 128)

            # Check that image.save was called with correct parameters
            image_mock.save.assert_called_once()
            args = image_mock.save.call_args[0]
            kwargs = image_mock.save.call_args[1]
            self.assertEqual(args[0], mock_byte_io)
            self.assertEqual(kwargs["format"], "PNG")

            # Check that ImageReader was called with the BytesIO
            mock_image_reader.assert_called_once_with(mock_byte_io)

            # Check that drawImage was called with correct parameters
            canvas_mock.drawImage.assert_called_once()
            args = canvas_mock.drawImage.call_args[0]
            kwargs = canvas_mock.drawImage.call_args[1]
            self.assertEqual(args[0], mock_image_reader.return_value)
            self.assertEqual(args[1], 100)
            self.assertEqual(args[2], 200)
            self.assertEqual(args[3], 300)
            self.assertEqual(args[4], 400)
            self.assertEqual(kwargs["mask"], "auto")

    @patch("app.services.pdf_generator.draw_background_image")
    def test_setup_new_page(self, mock_draw_bg):
        # Mock canvas
        canvas_mock = MagicMock(spec=canvas.Canvas)

        # Mock image stream
        image_stream = io.BytesIO(b"test image data")

        # Call the function
        result = setup_new_page(canvas_mock, image_stream)

        # Check that showPage was called
        canvas_mock.showPage.assert_called_once()

        # Check that setPageSize was called with landscape orientation
        canvas_mock.setPageSize.assert_called_once()
        args = canvas_mock.setPageSize.call_args[0]
        self.assertEqual(args[0], landscape((1200, 675)))

        # Check that draw_background_image was called with correct parameters
        mock_draw_bg.assert_called_once()
        args = mock_draw_bg.call_args[0]
        self.assertEqual(args[0], canvas_mock)
        self.assertEqual(args[1], image_stream)
        self.assertEqual(args[2], 1200)
        self.assertEqual(args[3], 675)

        # Check that the result is the correct y position
        self.assertEqual(result, 675 - (675 * 1 / 20))

    @patch("app.services.pdf_generator.draw_background_image")
    def test_setup_new_page_error(self, mock_draw_bg):
        # Mock canvas
        canvas_mock = MagicMock(spec=canvas.Canvas)

        # Mock image stream
        image_stream = io.BytesIO(b"test image data")

        # Mock draw_background_image to raise an exception
        mock_draw_bg.side_effect = Exception("Test error")

        # Call the function
        result = setup_new_page(canvas_mock, image_stream)

        # Check that showPage and setPageSize were still called
        canvas_mock.showPage.assert_called_once()
        canvas_mock.setPageSize.assert_called_once()

        # Check that the result is the correct y position despite the error
        self.assertEqual(result, 675 - (675 * 1 / 20))

    @patch("app.services.pdf_generator.pdfmetrics")
    def test_wrap_text(self, mock_pdfmetrics):
        # Mock stringWidth to simulate text width
        def mock_string_width(text, font, size):
            # Return a width proportional to the text length
            return len(text) * 10

        mock_pdfmetrics.stringWidth.side_effect = mock_string_width

        # Mock getRegisteredFontNames
        mock_pdfmetrics.getRegisteredFontNames.return_value = ["Helvetica"]

        # Test with text that fits on one line
        text = "Short text"
        lines, height = wrap_text(text, "Helvetica", 12, 200)

        # Check that the text was not wrapped
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], text)
        self.assertEqual(height, 12)

        # Test with text that needs to be wrapped
        text = "This is a longer text that should be wrapped because it exceeds the maximum width"
        lines, height = wrap_text(text, "Helvetica", 12, 200)

        # Check that the text was wrapped into multiple lines
        self.assertTrue(len(lines) > 1)
        self.assertEqual(height, 12 * len(lines))

        # Test with text containing line breaks
        text = "Line 1\nLine 2\nLine 3"
        lines, height = wrap_text(text, "Helvetica", 12, 200)

        # Check that the original line breaks were preserved
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "Line 1")
        self.assertEqual(lines[1], "Line 2")
        self.assertEqual(lines[2], "Line 3")
        self.assertEqual(height, 12 * 3)

    @patch("app.services.pdf_generator.canvas.Canvas")
    @patch("app.services.pdf_generator.datetime")
    @patch("app.services.pdf_generator.wrap_text")
    @patch("app.services.pdf_generator.pdfmetrics")
    def test_create_pdf(self, mock_pdfmetrics, mock_wrap_text, mock_datetime, mock_canvas):
        # Mock datetime.now
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2023-01-15"
        mock_datetime.now.return_value = mock_now

        # Mock Canvas instance
        canvas_instance = MagicMock()
        mock_canvas.return_value = canvas_instance

        # Mock wrap_text to return predefined values
        mock_wrap_text.return_value = (["Test Event"], 30)

        # Mock pdfmetrics
        mock_pdfmetrics.getRegisteredFontNames.return_value = []
        mock_pdfmetrics.stringWidth.return_value = 50  # Simuliere eine Textbreite

        # Mock appointments
        appointments = [
            {
                "id": "1_101",
                "description": "Test Event",
                "startDate": "2023-01-15T10:00:00Z",
                "endDate": "2023-01-15T12:00:00Z",
                "information": "Test Info",
                "meetingAt": "Test Location",
                "startDateView": "15.01.2023",
                "startTimeView": "11:00",
                "endTimeView": "13:00",
                "additional_info": "Additional Info",
            }
        ]

        # Mock parse_iso_datetime
        with patch("app.services.pdf_generator.parse_iso_datetime") as mock_parse:
            # Create a mock datetime object
            mock_dt = MagicMock()
            mock_dt.strftime.side_effect = lambda fmt: "15.01.2023" if fmt == "%d.%m.%Y" else "11:00"
            mock_parse.return_value = mock_dt

            # Mock format_date
            with patch("app.services.pdf_generator.format_date") as mock_format:
                mock_format.return_value = "Sonntag"

                # Call the function
                result = create_pdf(
                    appointments,
                    "#c1540c",  # date_color
                    "#ffffff",  # background_color
                    "#4e4e4e",  # description_color
                    128,  # alpha
                    None,  # image_stream
                )

        # Check that Canvas was created with the correct file path
        expected_path = os.path.join(self.config_mock["FILE_DIRECTORY"], "2023-01-15_Termine.pdf")
        mock_canvas.assert_called_once()
        args = mock_canvas.call_args[0]
        kwargs = mock_canvas.call_args[1]
        self.assertEqual(args[0], expected_path)
        self.assertEqual(kwargs["pagesize"], landscape((1200, 675)))

        # Check that the canvas methods were called
        canvas_instance.setTitle.assert_called_once_with("2023-01-15_Termine.pdf")
        canvas_instance.save.assert_called_once()

        # Check that the result is the correct filename
        self.assertEqual(result, "2023-01-15_Termine.pdf")


class TestDrawEventOverflow(unittest.TestCase):
    """Integration test: verify all drawn text stays within the grey box boundaries.

    Uses real reportlab canvas + font metrics to catch layout overflow regressions.
    """

    # Outlier events (ids 11-15) from scripts/preview_pdf.py — stress-test every layout area
    OUTLIER_EVENTS = [
        {
            "id": "11",
            "description": "Regionaler Jugendgottesdienst",
            "startDate": "2026-03-27T17:00:00Z",
            "endDate": "2026-03-27T19:00:00Z",
            "meetingAt": (
                "Evangelisches Gemeindezentrum an der Kreuzbergstraße 147, "
                "Eingang über den Hinterhof neben dem Parkplatz"
            ),
            "information": "",
            "additional_info": "Thema: Glaube und Zweifel",
        },
        {
            "id": "12",
            "description": (
                "Festlicher Gemeinschaftsgottesdienst mit Einführung der neuen Kirchenvorsteherin "
                "und anschließendem Empfang im Gemeindehaus mit Kaffee und Kuchen für alle Gemeindemitglieder"
            ),
            "startDate": "2026-03-29T10:00:00Z",
            "endDate": "2026-03-29T12:30:00Z",
            "meetingAt": "Stadtkirche",
            "information": "",
            "additional_info": "Bitte Kuchen mitbringen!",
        },
        {
            "id": "13",
            "description": "Karfreitagsgottesdienst",
            "startDate": "2026-04-03T10:00:00Z",
            "endDate": "2026-04-03T11:30:00Z",
            "meetingAt": "Stadtkirche",
            "information": "",
            "additional_info": (
                "Wochenspruch: Also hat Gott die Welt geliebt, dass er seinen "
                "eingeborenen Sohn gab, damit alle, die an ihn glauben, nicht "
                "verloren werden, sondern das ewige Leben haben. (Johannes 3,16)\n"
                "Wochenlied: O Haupt voll Blut und Wunden (EG 85)\n"
                "Predigttext: Jesaja 52,13–53,12\n"
                "Liturgische Farbe: Schwarz/Violett\n"
                "Kollekte: Brot für die Welt\n"
                "Musik: Kirchenchor – »O Traurigkeit, o Herzeleid«\n"
                "Orgel: Johann Sebastian Bach – »O Mensch, bewein dein Sünde groß« BWV 622\n"
                "Stille Prozession zum Kreuz mit Fürbitten\n"
                "Abendmahl in beiderlei Gestalt\n"
                "Anschließend stilles Beisammensein im Gemeindehaus"
            ),
        },
        {
            "id": "14",
            "description": (
                "Ökumenischer Gottesdienst zum Tag der Deutschen Einheit mit Friedensgebet "
                "und Segnung der neuen Gemeindefahne durch Superintendent Dr. Hoffmann"
            ),
            "startDate": "2026-04-05T10:00:00Z",
            "endDate": "2026-04-05T12:00:00Z",
            "meetingAt": (
                "Evangelisch-Lutherische Hauptkirche St. Petri am Alten Marktplatz, Seiteneingang barrierefrei"
            ),
            "information": "",
            "additional_info": (
                "Mitwirkende: Posaunenchor, Gospelchor »Joyful Noise«, Bläserensemble der Musikschule\n"
                "Predigt: Superintendent Dr. Hoffmann und Pfarrer Benedikt (kath.)\n"
                "Kollekte: Renovierung des Gemeindehauses\n"
                "Anschließend Stehempfang auf dem Kirchplatz bei hoffentlich gutem Wetter\n"
                "Kinderbetreuung im Gemeindehaus während des gesamten Gottesdienstes"
            ),
        },
        {
            "id": "15",
            "description": "Gemeindeausflug",
            "startDate": "2026-04-07T08:00:00Z",
            "endDate": "2026-04-07T18:00:00Z",
            "meetingAt": "",
            "information": (
                "Abfahrt: 08:00 Uhr am Gemeindehaus (bitte pünktlich!). "
                "Ziel: Kloster Maulbronn mit Führung und anschließender Wanderung "
                "durch das Salzachtal. Mittagessen im Klosterhof (Selbstzahler). "
                "Nachmittags freie Zeit für Besichtigung oder Spaziergang. "
                "Rückfahrt gegen 17:00 Uhr. Kosten: 15 € pro Person (Busfahrt + Eintritt). "
                "Anmeldung bis 25.03. im Pfarrbüro. Bitte festes Schuhwerk mitbringen!"
            ),
            "additional_info": "",
        },
    ]

    def setUp(self):
        import app.services.pdf_generator as pg

        # Reset font cache so we get a fresh registration with real fonts
        pg._cached_fonts = None
        self.font_name, self.font_name_bold = pg._register_fonts()
        self.y_start = pg.PAGE_HEIGHT - pg.BOTTOM_MARGIN

    def _draw_and_capture(self, event):
        """Draw a single event on a real canvas and capture box + text positions.

        Returns (box_calls, text_calls) where:
          box_calls  = list of (x, y_bottom, width, height)
          text_calls = list of (x, y, text)
        """
        from app.services.pdf_generator import _draw_event

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=landscape((1200, 675)))

        box_calls = []
        text_calls = []

        original_draw_string = c.drawString

        def spy_draw_string(x, y, text, *args, **kwargs):
            text_calls.append((x, y, text))
            return original_draw_string(x, y, text, *args, **kwargs)

        c.drawString = spy_draw_string

        with patch(
            "app.services.pdf_generator.draw_transparent_rectangle",
            wraps=draw_transparent_rectangle,
        ) as mock_rect:
            _draw_event(
                c,
                event,
                self.y_start,
                self.font_name,
                self.font_name_bold,
                date_color="#FFFFFF",
                background_color="#000000",
                description_color="#CCCCCC",
                alpha=180,
                image_stream=None,
            )

            for call in mock_rect.call_args_list:
                # draw_transparent_rectangle(canvas, x, y, width, height, ...)
                _, x, y_bottom, width, height = call[0][:5]
                box_calls.append((x, y_bottom, width, height))

        return box_calls, text_calls

    def test_text_stays_within_box_vertically(self):
        """No drawString baseline should fall below the grey box bottom edge."""
        for event in self.OUTLIER_EVENTS:
            with self.subTest(event_id=event["id"]):
                box_calls, text_calls = self._draw_and_capture(event)
                self.assertTrue(box_calls, "No box was drawn")
                self.assertTrue(text_calls, "No text was drawn")

                box_x, box_y_bottom, box_w, box_h = box_calls[0]
                min_text_y = min(y for _, y, _ in text_calls)

                self.assertGreaterEqual(
                    min_text_y,
                    box_y_bottom,
                    f"Event {event['id']}: text baseline {min_text_y:.1f} is below "
                    f"box bottom {box_y_bottom:.1f} (overflow by {box_y_bottom - min_text_y:.1f}pt)",
                )

    def test_text_stays_within_box_horizontally(self):
        """No drawString right edge should exceed the grey box right edge."""
        for event in self.OUTLIER_EVENTS:
            with self.subTest(event_id=event["id"]):
                box_calls, text_calls = self._draw_and_capture(event)
                self.assertTrue(box_calls, "No box was drawn")
                self.assertTrue(text_calls, "No text was drawn")

                box_x, box_y_bottom, box_w, box_h = box_calls[0]
                box_right = box_x + box_w

                # Check each text string's right edge using real font metrics
                for text_x, text_y, text in text_calls:
                    text_width = pdfmetrics.stringWidth(text, self.font_name, 25)
                    text_right = text_x + text_width
                    self.assertLessEqual(
                        text_right,
                        box_right + 1.0,  # 1pt tolerance for rounding
                        f"Event {event['id']}: text '{text[:40]}…' right edge {text_right:.1f} "
                        f"exceeds box right {box_right:.1f}",
                    )


if __name__ == "__main__":
    unittest.main()
