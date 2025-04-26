import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
from PIL import Image
from tests.conftest import TestConfig


class TestPdfGenerator:
    @patch('app.pdf_generator.canvas.Canvas')
    @patch('app.pdf_generator.ImageReader')
    @patch('app.pdf_generator.pdfmetrics')
    def test_create_pdf_without_background(self, mock_pdfmetrics, mock_image_reader, mock_canvas, app_context):
        from app.pdf_generator import create_pdf
        
        mock_canvas_instance = MagicMock()
        mock_canvas.return_value = mock_canvas_instance
        
        mock_pdfmetrics.getRegisteredFontNames.return_value = ['Bahnschrift']
        mock_pdfmetrics.stringWidth.return_value = 100
        
        appointments = [
            {
                'id': '1_123',
                'description': 'Test Appointment 1',
                'startDate': '2023-01-01T10:00:00Z',
                'endDate': '2023-01-01T11:00:00Z',
                'meetingAt': 'Test Location 1',
                'information': 'Test Info 1',
                'startDateView': '01.01.2023',
                'startTimeView': '10:00',
                'endTimeView': '11:00',
                'additional_info': 'Additional Info 1'
            },
            {
                'id': '1_456',
                'description': 'Test Appointment 2',
                'startDate': '2023-01-02T10:00:00Z',
                'endDate': '2023-01-02T11:00:00Z',
                'meetingAt': 'Test Location 2',
                'information': 'Test Info 2',
                'startDateView': '02.01.2023',
                'startTimeView': '10:00',
                'endTimeView': '11:00',
                'additional_info': 'Additional Info 2'
            }
        ]
        
        filename = create_pdf(appointments, '#c1540c', '#ffffff', '#4e4e4e', 128, None)
        
        assert filename.endswith('.pdf')
        
        mock_canvas_instance.setFont.assert_called()
        mock_canvas_instance.drawString.assert_called()
        mock_canvas_instance.save.assert_called_once()

    @patch('app.pdf_generator.canvas.Canvas')
    @patch('app.pdf_generator.ImageReader')
    @patch('app.pdf_generator.pdfmetrics')
    def test_create_pdf_with_background(self, mock_pdfmetrics, mock_image_reader, mock_canvas, app_context):
        from app.pdf_generator import create_pdf
        
        mock_canvas_instance = MagicMock()
        mock_canvas.return_value = mock_canvas_instance
        
        mock_image_reader_instance = MagicMock()
        mock_image_reader_instance.getSize.return_value = (800, 600)
        mock_image_reader.return_value = mock_image_reader_instance
        
        mock_pdfmetrics.getRegisteredFontNames.return_value = ['Bahnschrift']
        mock_pdfmetrics.stringWidth.return_value = 100
        
        appointments = [
            {
                'id': '1_123',
                'description': 'Test Appointment 1',
                'startDate': '2023-01-01T10:00:00Z',
                'endDate': '2023-01-01T11:00:00Z',
                'meetingAt': 'Test Location 1',
                'information': 'Test Info 1',
                'startDateView': '01.01.2023',
                'startTimeView': '10:00',
                'endTimeView': '11:00',
                'additional_info': 'Additional Info 1'
            }
        ]
        
        background_image_stream = BytesIO(b'test')
        
        filename = create_pdf(appointments, '#c1540c', '#ffffff', '#4e4e4e', 128, background_image_stream)
        
        assert filename.endswith('.pdf')
        
        mock_canvas_instance.setFont.assert_called()
        mock_canvas_instance.drawString.assert_called()
        mock_canvas_instance.save.assert_called_once()
        
        mock_canvas_instance.drawImage.assert_called()

    @patch('app.pdf_generator.ImageReader')
    def test_draw_transparent_rectangle(self, mock_image_reader, app_context):
        from app.pdf_generator import draw_transparent_rectangle, create_transparent_image
        
        mock_image_reader_instance = MagicMock()
        mock_image_reader.return_value = mock_image_reader_instance
        
        mock_canvas = MagicMock()
        
        with patch('app.pdf_generator.create_transparent_image') as mock_create_transparent_image:
            from PIL import Image
            test_image = Image.new('RGBA', (100, 50), (255, 255, 255, 128))
            mock_create_transparent_image.return_value = test_image
            
            draw_transparent_rectangle(mock_canvas, 10, 20, 100, 50, '#ffffff', 128)
            
            mock_create_transparent_image.assert_called_once_with(100, 50, '#ffffff', 128)
        
        mock_canvas.drawImage.assert_called_once()

    def test_create_transparent_image(self, app_context):
        from app.pdf_generator import create_transparent_image
        from PIL import Image
        
        image = create_transparent_image(100, 50, '#ffffff', 128)
        
        assert isinstance(image, Image.Image)
        assert image.mode == 'RGBA'
        assert image.size == (100, 50)
        
        colors = ['#ffffff', '#000000', '#ff0000', '#00ff00', '#0000ff']
        alpha_values = [0, 64, 128, 192, 255]
        
        for color in colors:
            for alpha in alpha_values:
                image = create_transparent_image(100, 50, color, alpha)
                
                assert isinstance(image, Image.Image)
                assert image.mode == 'RGBA'
                assert image.size == (100, 50)
                
                pixel = image.getpixel((50, 25))
                assert len(pixel) == 4
                assert pixel[3] == alpha

    @patch('app.pdf_generator.ImageReader')
    def test_draw_background_image(self, mock_image_reader, app_context):
        from app.pdf_generator import draw_background_image
        
        mock_image_reader_instance = MagicMock()
        mock_image_reader_instance.getSize.return_value = (800, 600)
        mock_image_reader.return_value = mock_image_reader_instance
        
        mock_canvas = MagicMock()
        
        image_stream = BytesIO(b'test')
        draw_background_image(mock_canvas, image_stream, 1200, 675)
        
        mock_image_reader.assert_called_once_with(image_stream)
        
        mock_image_reader_instance.getSize.assert_called_once()
        
        mock_canvas.drawImage.assert_called_once()

    def test_wrap_text_no_wrap_needed(self, app_context):
        from app.pdf_generator import wrap_text
        
        with patch('app.pdf_generator.pdfmetrics') as mock_pdfmetrics:
            mock_pdfmetrics.getRegisteredFontNames.return_value = ['Bahnschrift']
            mock_pdfmetrics.stringWidth.return_value = 50
            
            text = "This is a short text."
            font_name = "Bahnschrift"
            line_height = 12
            max_width = 100
            
            wrapped_lines, text_height = wrap_text(text, font_name, line_height, max_width)
            
            assert len(wrapped_lines) == 1
            assert wrapped_lines[0] == text
            assert text_height == line_height

    def test_wrap_text_with_wrap_needed(self, app_context):
        from app.pdf_generator import wrap_text
        
        with patch('app.pdf_generator.pdfmetrics') as mock_pdfmetrics:
            mock_pdfmetrics.getRegisteredFontNames.return_value = ['Bahnschrift']
            
            def mock_string_width(text, font, size):
                return 150 if len(text.split()) > 3 else 50
            
            mock_pdfmetrics.stringWidth.side_effect = mock_string_width
            
            text = "This is a long text that needs to be wrapped."
            font_name = "Bahnschrift"
            line_height = 12
            max_width = 100
            
            wrapped_lines, text_height = wrap_text(text, font_name, line_height, max_width)
            
            assert len(wrapped_lines) > 1
            assert text_height > line_height

    def test_wrap_text_with_newlines(self, app_context):
        from app.pdf_generator import wrap_text
        
        with patch('app.pdf_generator.pdfmetrics') as mock_pdfmetrics:
            mock_pdfmetrics.getRegisteredFontNames.return_value = ['Bahnschrift']
            mock_pdfmetrics.stringWidth.return_value = 50
            
            text = "Line 1\nLine 2\nLine 3"
            font_name = "Bahnschrift"
            line_height = 12
            max_width = 100
            
            wrapped_lines, text_height = wrap_text(text, font_name, line_height, max_width)
            
            assert len(wrapped_lines) == 3
            assert wrapped_lines[0] == "Line 1"
            assert wrapped_lines[1] == "Line 2"
            assert wrapped_lines[2] == "Line 3"
            assert text_height == 3 * line_height

    @patch('app.pdf_generator.canvas.Canvas')
    def test_setup_new_page_without_image(self, mock_canvas, app_context):
        from app.pdf_generator import setup_new_page
        
        mock_canvas_instance = MagicMock()
        mock_canvas.return_value = mock_canvas_instance
        
        y_position = setup_new_page(mock_canvas_instance, None)
        
        mock_canvas_instance.showPage.assert_called_once()
        
        mock_canvas_instance.setPageSize.assert_called_once()
        
        assert y_position > 0

    @patch('app.pdf_generator.canvas.Canvas')
    @patch('app.pdf_generator.draw_background_image')
    def test_setup_new_page_with_image(self, mock_draw_background_image, mock_canvas, app_context):
        from app.pdf_generator import setup_new_page
        
        mock_canvas_instance = MagicMock()
        mock_canvas.return_value = mock_canvas_instance
        
        image_stream = BytesIO(b'test')
        y_position = setup_new_page(mock_canvas_instance, image_stream)
        
        mock_canvas_instance.showPage.assert_called_once()
        
        mock_canvas_instance.setPageSize.assert_called_once()
        
        mock_draw_background_image.assert_called_once()
        
        assert y_position > 0