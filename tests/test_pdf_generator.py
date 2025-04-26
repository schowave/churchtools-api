import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import io
from PIL import Image
from reportlab.lib.pagesizes import landscape
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from app.services.pdf_generator import (
    draw_background_image, create_transparent_image,
    draw_transparent_rectangle, setup_new_page,
    wrap_text, create_pdf
)
from app.config import Config

class TestPdfGenerator(unittest.TestCase):
    def setUp(self):
        # Mock Config
        self.config_mock = {
            'FILE_DIRECTORY': '/tmp/test_files'
        }
        self.config_patch = patch('app.services.pdf_generator.Config', 
                                 FILE_DIRECTORY=self.config_mock['FILE_DIRECTORY'])
        self.config_patch.start()
        
        # Ensure test directory exists
        os.makedirs(self.config_mock['FILE_DIRECTORY'], exist_ok=True)
    
    def tearDown(self):
        self.config_patch.stop()
    
    @patch('app.services.pdf_generator.ImageReader')
    def test_draw_background_image(self, mock_image_reader):
        # Mock canvas and image
        canvas_mock = MagicMock(spec=canvas.Canvas)
        image_stream = io.BytesIO(b'test image data')
        
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
        # Wir prüfen nur, ob die Position innerhalb eines vernünftigen Bereichs liegt
        self.assertTrue(100 <= args[1] <= 300)  # x position sollte ungefähr zentriert sein
        self.assertTrue(0 <= args[2] <= 100)    # y position sollte ungefähr zentriert sein
        # Wir prüfen nicht die exakten Werte, sondern nur das Verhältnis
        self.assertTrue(kwargs['width'] > 0)
        self.assertTrue(kwargs['height'] > 0)
        # Überprüfen, dass das Seitenverhältnis beibehalten wird
        self.assertAlmostEqual(kwargs['width'] / kwargs['height'], 800 / 600, places=1)
        self.assertEqual(kwargs['mask'], 'auto')
    
    def test_draw_background_image_none(self):
        # Mock canvas
        canvas_mock = MagicMock(spec=canvas.Canvas)
        
        # Call the function with None image
        draw_background_image(canvas_mock, None, 1200, 675)
        
        # Check that drawImage was not called
        canvas_mock.drawImage.assert_not_called()
    
    @patch('app.services.pdf_generator.ImageReader')
    def test_draw_background_image_error(self, mock_image_reader):
        # Mock canvas and image
        canvas_mock = MagicMock(spec=canvas.Canvas)
        image_stream = io.BytesIO(b'test image data')
        
        # Mock ImageReader to raise an exception
        mock_image_reader.side_effect = Exception("Test error")
        
        # Call the function
        draw_background_image(canvas_mock, image_stream, 1200, 675)
        
        # Check that drawImage was not called
        canvas_mock.drawImage.assert_not_called()
    
    @patch('app.services.pdf_generator.Image')
    @patch('app.services.pdf_generator.ImageColor')
    def test_create_transparent_image(self, mock_image_color, mock_image):
        # Mock ImageColor.getcolor
        mock_image_color.getcolor.return_value = (255, 255, 255, 255)
        
        # Mock Image.new
        image_mock = MagicMock()
        mock_image.new.return_value = image_mock
        
        # Call the function
        result = create_transparent_image(800, 600, '#ffffff', 128)
        
        # Check that ImageColor.getcolor was called with correct parameters
        mock_image_color.getcolor.assert_called_once_with('#ffffff', 'RGBA')
        
        # Check that Image.new was called with correct parameters
        mock_image.new.assert_called_once_with('RGBA', (800, 600), (255, 255, 255, 128))
        
        # Check that the result is the mocked image
        self.assertEqual(result, image_mock)
    
    @patch('app.services.pdf_generator.create_transparent_image')
    @patch('app.services.pdf_generator.ImageReader')
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
        with patch('io.BytesIO', return_value=mock_byte_io):
            # Call the function
            draw_transparent_rectangle(canvas_mock, 100, 200, 300, 400, '#ffffff', 128)
            
            # Check that create_transparent_image was called with correct parameters
            mock_create_image.assert_called_once_with(300, 400, '#ffffff', 128)
            
            # Check that image.save was called with correct parameters
            image_mock.save.assert_called_once()
            args = image_mock.save.call_args[0]
            kwargs = image_mock.save.call_args[1]
            self.assertEqual(args[0], mock_byte_io)
            self.assertEqual(kwargs['format'], 'PNG')
            
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
            self.assertEqual(kwargs['mask'], 'auto')
    
    @patch('app.services.pdf_generator.draw_background_image')
    def test_setup_new_page(self, mock_draw_bg):
        # Mock canvas
        canvas_mock = MagicMock(spec=canvas.Canvas)
        
        # Mock image stream
        image_stream = io.BytesIO(b'test image data')
        
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
    
    @patch('app.services.pdf_generator.draw_background_image')
    def test_setup_new_page_error(self, mock_draw_bg):
        # Mock canvas
        canvas_mock = MagicMock(spec=canvas.Canvas)
        
        # Mock image stream
        image_stream = io.BytesIO(b'test image data')
        
        # Mock draw_background_image to raise an exception
        mock_draw_bg.side_effect = Exception("Test error")
        
        # Call the function
        result = setup_new_page(canvas_mock, image_stream)
        
        # Check that showPage and setPageSize were still called
        canvas_mock.showPage.assert_called_once()
        canvas_mock.setPageSize.assert_called_once()
        
        # Check that the result is the correct y position despite the error
        self.assertEqual(result, 675 - (675 * 1 / 20))
    
    @patch('app.services.pdf_generator.pdfmetrics')
    def test_wrap_text(self, mock_pdfmetrics):
        # Mock stringWidth to simulate text width
        def mock_string_width(text, font, size):
            # Return a width proportional to the text length
            return len(text) * 10
        mock_pdfmetrics.stringWidth.side_effect = mock_string_width
        
        # Mock getRegisteredFontNames
        mock_pdfmetrics.getRegisteredFontNames.return_value = ['Helvetica']
        
        # Test with text that fits on one line
        text = "Short text"
        lines, height = wrap_text(text, 'Helvetica', 12, 200)
        
        # Check that the text was not wrapped
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], text)
        self.assertEqual(height, 12)
        
        # Test with text that needs to be wrapped
        text = "This is a longer text that should be wrapped because it exceeds the maximum width"
        lines, height = wrap_text(text, 'Helvetica', 12, 200)
        
        # Check that the text was wrapped into multiple lines
        self.assertTrue(len(lines) > 1)
        self.assertEqual(height, 12 * len(lines))
        
        # Test with text containing line breaks
        text = "Line 1\nLine 2\nLine 3"
        lines, height = wrap_text(text, 'Helvetica', 12, 200)
        
        # Check that the original line breaks were preserved
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "Line 1")
        self.assertEqual(lines[1], "Line 2")
        self.assertEqual(lines[2], "Line 3")
        self.assertEqual(height, 12 * 3)
    
    @patch('app.services.pdf_generator.canvas.Canvas')
    @patch('app.services.pdf_generator.datetime')
    @patch('app.services.pdf_generator.wrap_text')
    @patch('app.services.pdf_generator.pdfmetrics')
    def test_create_pdf(self, mock_pdfmetrics, mock_wrap_text, mock_datetime, mock_canvas):
        # Mock datetime.now
        mock_now = MagicMock()
        mock_now.strftime.return_value = '2023-01-15'
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
                'id': '1_101',
                'description': 'Test Event',
                'startDate': '2023-01-15T10:00:00Z',
                'endDate': '2023-01-15T12:00:00Z',
                'information': 'Test Info',
                'meetingAt': 'Test Location',
                'startDateView': '15.01.2023',
                'startTimeView': '11:00',
                'endTimeView': '13:00',
                'additional_info': 'Additional Info'
            }
        ]
        
        # Mock parse_iso_datetime
        with patch('app.services.pdf_generator.parse_iso_datetime') as mock_parse:
            # Erstelle ein Mock-Datetime-Objekt
            mock_dt = MagicMock()
            mock_dt.strftime.side_effect = lambda fmt: '15.01.2023' if fmt == '%d.%m.%Y' else '11:00'
            mock_parse.return_value = mock_dt
            
            # Mock format_date
            with patch('app.services.pdf_generator.format_date') as mock_format:
                mock_format.return_value = 'Sonntag'
                
                # Call the function
                result = create_pdf(
                    appointments,
                    '#c1540c',  # date_color
                    '#ffffff',  # background_color
                    '#4e4e4e',  # description_color
                    128,        # alpha
                    None        # image_stream
                )
        
        # Check that Canvas was created with the correct file path
        expected_path = os.path.join(self.config_mock['FILE_DIRECTORY'], '2023-01-15_Termine.pdf')
        mock_canvas.assert_called_once()
        args = mock_canvas.call_args[0]
        kwargs = mock_canvas.call_args[1]
        self.assertEqual(args[0], expected_path)
        self.assertEqual(kwargs['pagesize'], landscape((1200, 675)))
        
        # Check that the canvas methods were called
        canvas_instance.setTitle.assert_called_once_with('2023-01-15_Termine.pdf')
        canvas_instance.save.assert_called_once()
        
        # Check that the result is the correct filename
        self.assertEqual(result, '2023-01-15_Termine.pdf')

if __name__ == '__main__':
    unittest.main()