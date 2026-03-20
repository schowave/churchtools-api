import zipfile
from io import BytesIO

import structlog
from pdf2image import convert_from_bytes

logger = structlog.get_logger()


def handle_jpeg_generation(pdf_bytes: bytes) -> bytes:
    images = convert_from_bytes(pdf_bytes)
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for i, image in enumerate(images):
            jpeg_stream = BytesIO()
            image.save(jpeg_stream, "JPEG")
            zip_file.writestr(f"page_{i + 1}.jpg", jpeg_stream.getvalue())

    logger.info(f"JPEG images generated: {len(images)} pages")
    return zip_buffer.getvalue()
