from unittest.mock import MagicMock, patch

from app.services.jpeg_generator import handle_jpeg_generation


@patch("app.services.jpeg_generator.convert_from_bytes")
def test_handle_jpeg_generation(mock_convert):
    # Mock PDF to image conversion
    mock_image1 = MagicMock()
    mock_image2 = MagicMock()
    mock_convert.return_value = [mock_image1, mock_image2]

    # Mock image save method to write test data to BytesIO
    def mock_save(stream, format):
        stream.write(b"test image data")

    mock_image1.save.side_effect = mock_save
    mock_image2.save.side_effect = mock_save

    # Call the function with bytes input
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    result = handle_jpeg_generation(pdf_bytes)

    # Check that convert_from_bytes was called with the pdf bytes
    mock_convert.assert_called_once_with(pdf_bytes)

    # Check that the result is bytes (zip content)
    assert isinstance(result, bytes)
