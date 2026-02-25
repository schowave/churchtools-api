import logging
import os
import zipfile
from io import BytesIO

from pdf2image import convert_from_path

from app.config import Config

logger = logging.getLogger(__name__)


def handle_jpeg_generation(pdf_filename):
    full_pdf_path = os.path.join(Config.FILE_DIRECTORY, pdf_filename)
    images = convert_from_path(full_pdf_path)
    jpeg_files = []

    for i, image in enumerate(images):
        jpeg_stream = BytesIO()
        image.save(jpeg_stream, 'JPEG')
        jpeg_stream.seek(0)
        jpeg_files.append((f'page_{i + 1}.jpg', jpeg_stream))

    zip_filename = os.path.splitext(pdf_filename)[0] + ".zip"
    zip_path = os.path.join(Config.FILE_DIRECTORY, zip_filename)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, file_bytes in jpeg_files:
            zip_file.writestr(file_name, file_bytes.read())

    logger.info(f"JPEG images successfully created and packed into ZIP file: {zip_filename}")
    return zip_filename
