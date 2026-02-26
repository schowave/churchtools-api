import io
import logging
import os
from datetime import datetime

from babel.dates import format_date
from PIL import Image, ImageColor
from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.config import Config
from app.utils import normalize_newlines, parse_iso_datetime

logger = logging.getLogger(__name__)

# Layout constants (16:9 page for church projector display)
PAGE_WIDTH = 1200
PAGE_HEIGHT = 675
PAGE_SIZE = (PAGE_WIDTH, PAGE_HEIGHT)

# Grid
LEFT_COLUMN_X = PAGE_WIDTH / 27
RIGHT_COLUMN_X = PAGE_WIDTH * 2 / 5
INDENT = PAGE_WIDTH / 40
TOP_MARGIN = PAGE_HEIGHT / 15
BOTTOM_MARGIN = PAGE_HEIGHT / 20

# Typography (relative to page height)
BASE_FONT_SIZE = PAGE_HEIGHT / 27
SCALE_FACTOR = BASE_FONT_SIZE / 27
LINE_HEIGHT_FACTOR = 1.4
LINE_SPACING_FACTOR = 1.5
TOP_PADDING_FACTOR = 0.8

# Preferred font (Bahnschrift for church display, Helvetica as fallback)
PREFERRED_FONT = "Bahnschrift"
FALLBACK_FONT = "Helvetica"
FALLBACK_FONT_BOLD = "Helvetica-Bold"

# Resolve fonts/ directory relative to project root (two levels up from this file)
_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "fonts")

_cached_fonts = None


def _register_fonts():
    """Register preferred fonts with fallback to Helvetica.

    Returns (font_name, bold_font_name). Results are cached after first call.
    """
    global _cached_fonts
    if _cached_fonts is not None:
        return _cached_fonts

    font_name = PREFERRED_FONT
    try:
        if font_name not in pdfmetrics.getRegisteredFontNames():
            try:
                pdfmetrics.registerFont(TTFont(font_name, os.path.join(_FONTS_DIR, f"{font_name}.ttf")))
            except Exception as e:
                logger.error(f"Error registering font {font_name}: {e}")
                font_name = FALLBACK_FONT

        bold_font_name = font_name + "-Bold"
        if bold_font_name not in pdfmetrics.getRegisteredFontNames():
            try:
                if font_name == PREFERRED_FONT:
                    # Bahnschrift uses the same file for bold
                    pdfmetrics.registerFont(TTFont(bold_font_name, os.path.join(_FONTS_DIR, f"{font_name}.ttf")))
                else:
                    pdfmetrics.registerFont(TTFont(bold_font_name, os.path.join(_FONTS_DIR, f"{font_name}-Bold.ttf")))
            except Exception as e:
                logger.error(f"Error registering bold font {bold_font_name}: {e}")
                bold_font_name = FALLBACK_FONT_BOLD
                if FALLBACK_FONT_BOLD not in pdfmetrics.getRegisteredFontNames():
                    try:
                        pdfmetrics.registerFont(
                            TTFont(FALLBACK_FONT_BOLD, os.path.join(_FONTS_DIR, "helvetica-bold.ttf"))
                        )
                    except Exception as e2:
                        logger.error(f"Error registering font {FALLBACK_FONT_BOLD}: {e2}")
                        bold_font_name = FALLBACK_FONT
    except Exception as e:
        logger.error(f"General error in font registration: {e}")
        font_name = FALLBACK_FONT
        bold_font_name = FALLBACK_FONT_BOLD

    _cached_fonts = (font_name, bold_font_name)
    return _cached_fonts


def draw_background_image(canvas, image_stream, page_width, page_height):
    if image_stream is None:
        return

    try:
        image = ImageReader(image_stream)
        image_width, image_height = image.getSize()

        width_scale = page_width / image_width
        height_scale = page_height / image_height
        scale = min(width_scale, height_scale)

        scaled_width = image_width * scale
        scaled_height = image_height * scale

        x_position = (page_width - scaled_width) / 2
        y_position = (page_height - scaled_height) / 2

        canvas.drawImage(image, x_position, y_position, width=scaled_width, height=scaled_height, mask="auto")
    except Exception as e:
        logger.error(f"Error drawing background image: {e}")


def create_transparent_image(width, height, background_color, alpha):
    width = int(width)
    height = int(height)

    rgba_color = ImageColor.getcolor(background_color, "RGBA")
    rgba_color = rgba_color[:-1] + (int(alpha),)

    return Image.new("RGBA", (width, height), rgba_color)


def draw_transparent_rectangle(canvas, x, y, width, height, background_color, alpha):
    transparent_image = create_transparent_image(width, height, background_color, alpha)

    img_byte_arr = io.BytesIO()
    transparent_image.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)

    canvas.drawImage(ImageReader(img_byte_arr), x, y, width, height, mask="auto")


def setup_new_page(canvas_obj, image_stream):
    canvas_obj.showPage()
    canvas_obj.setPageSize(landscape(PAGE_SIZE))
    new_y_position = PAGE_HEIGHT - BOTTOM_MARGIN
    try:
        if image_stream:
            draw_background_image(canvas_obj, image_stream, *landscape(PAGE_SIZE))
    except Exception as e:
        logger.error(f"Error setting up a new page: {e}")
    return new_y_position


def wrap_text(text, font_name, line_height, max_width):
    """Wrap text to fit within a given width when rendered in a given font and size.

    Returns a list of lines and the total height the text block will require.
    Preserves original line breaks and wraps text that exceeds max_width.
    """
    # Ensure fonts are registered (idempotent after first call)
    _register_fonts()

    wrapped_lines = []
    text_height = 0

    original_lines = text.split("\n")

    for line in original_lines:
        if pdfmetrics.stringWidth(line, font_name, line_height) <= max_width:
            wrapped_lines.append(line)
            text_height += line_height
        else:
            words = line.split()
            wrapped_line = []
            while words:
                wrapped_line.append(words.pop(0))
                test_line = " ".join(wrapped_line + words[:1])
                if pdfmetrics.stringWidth(test_line, font_name, line_height) > max_width:
                    wrapped_lines.append(" ".join(wrapped_line))
                    text_height += line_height
                    wrapped_line = []
            if wrapped_line:
                wrapped_lines.append(" ".join(wrapped_line))
                text_height += line_height

    return wrapped_lines, text_height


def _draw_event(
    c,
    event,
    y_position,
    font_name,
    font_name_bold,
    date_color,
    background_color,
    description_color,
    alpha,
    image_stream,
):
    """Draw a single event on the PDF canvas. Returns the updated y_position."""
    # Derived typography sizes
    font_size_large = BASE_FONT_SIZE * LINE_SPACING_FACTOR
    line_height_large = font_size_large * LINE_HEIGHT_FACTOR
    font_size_medium = BASE_FONT_SIZE * 1.2
    line_height_medium = font_size_medium * LINE_HEIGHT_FACTOR
    line_height_small = BASE_FONT_SIZE * LINE_HEIGHT_FACTOR
    line_spacing = BASE_FONT_SIZE * LINE_SPACING_FACTOR
    top_padding = BASE_FONT_SIZE * TOP_PADDING_FACTOR
    rect_width = PAGE_WIDTH * SCALE_FACTOR

    wrapped_description_lines, _ = wrap_text(
        event["description"], font_name_bold, font_size_large, PAGE_WIDTH - RIGHT_COLUMN_X - INDENT
    )

    # Calculate the total text block height (using actual drawing step size)
    description_step = font_size_large * LINE_SPACING_FACTOR
    total_text_height = top_padding + len(wrapped_description_lines) * description_step

    information = normalize_newlines(event.get("additional_info") or event.get("information") or "")
    info_max_width = LEFT_COLUMN_X + rect_width - RIGHT_COLUMN_X - INDENT
    wrapped_info_lines, _ = wrap_text(information, font_name, font_size_medium, info_max_width)

    left_col_max_width = RIGHT_COLUMN_X - LEFT_COLUMN_X - INDENT * 2
    wrapped_meeting_at_lines, _ = (
        wrap_text(event["meetingAt"], font_name, font_size_medium, left_col_max_width)
        if event["meetingAt"]
        else ([], 0)
    )

    meeting_at_line_count = len(wrapped_meeting_at_lines) if event["meetingAt"] else 0
    medium_step = font_size_medium * LINE_SPACING_FACTOR
    time_and_meeting_at_height = line_height_medium + meeting_at_line_count * medium_step

    info_step = font_size_medium * LINE_SPACING_FACTOR
    actual_info_height = len(wrapped_info_lines) * info_step
    wrapped_info_height_with_padding = (actual_info_height + line_height_small) if information != "" else 0

    max_height = max(wrapped_info_height_with_padding, time_and_meeting_at_height)
    rect_height = total_text_height + max_height + line_height_medium

    # Check if we need to start a new page
    if y_position < (rect_height + BOTTOM_MARGIN):
        y_position = setup_new_page(c, image_stream)

    draw_transparent_rectangle(
        c, LEFT_COLUMN_X, y_position - rect_height, rect_width, rect_height, background_color, alpha
    )

    text_y_position = y_position - top_padding

    # Left column: German Day and Date
    c.setFillColor(HexColor(date_color))
    c.setFont(font_name_bold, font_size_large)

    start_dt = parse_iso_datetime(event["startDate"])
    end_dt = parse_iso_datetime(event["endDate"])
    german_day_of_week = format_date(start_dt, format="EEEE", locale="de_DE")
    day_date_str = f"{german_day_of_week}, {start_dt.strftime('%d.%m.%Y')}"
    c.drawString(LEFT_COLUMN_X + INDENT, text_y_position - line_height_large, day_date_str)

    # Time
    c.setFillColor(HexColor(description_color))
    c.setFont(font_name, font_size_medium)
    time_str = f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')} Uhr"
    c.drawString(LEFT_COLUMN_X + INDENT, text_y_position - line_height_large - line_height_medium, time_str)

    # MeetingAt (wrapped to left column width)
    if event["meetingAt"]:
        meeting_at_y = text_y_position - line_height_large - line_height_medium - line_height_medium
        for ma_line in wrapped_meeting_at_lines:
            c.drawString(LEFT_COLUMN_X + INDENT, meeting_at_y, ma_line)
            meeting_at_y -= font_size_medium * LINE_SPACING_FACTOR

    # Right column: Caption and Information
    c.setFillColor(black)
    c.setFont(font_name_bold, font_size_large)

    description_y_position = text_y_position - line_height_large
    for line in wrapped_description_lines:
        c.drawString(RIGHT_COLUMN_X, description_y_position, line)
        description_y_position -= font_size_large * LINE_SPACING_FACTOR

    information_y_position = description_y_position

    c.setFillColor(HexColor(description_color))
    c.setFont(font_name, font_size_medium)

    for detail in wrapped_info_lines:
        c.drawString(RIGHT_COLUMN_X, information_y_position, detail)
        information_y_position -= font_size_medium * LINE_SPACING_FACTOR

    return min(information_y_position, y_position - rect_height - line_spacing)


def create_pdf(appointments, date_color, background_color, description_color, alpha, image_stream=None):
    font_name, font_name_bold = _register_fonts()

    current_day = datetime.now().strftime("%Y-%m-%d")
    filename = f"{current_day}_Termine.pdf"
    file_path = os.path.join(Config.FILE_DIRECTORY, filename)
    c = canvas.Canvas(file_path, pagesize=landscape(PAGE_SIZE))
    c.setTitle(filename)

    try:
        if image_stream:
            draw_background_image(c, image_stream, *landscape(PAGE_SIZE))
    except Exception as e:
        logger.error(f"Error drawing background image: {e}")

    y_position = PAGE_HEIGHT - TOP_MARGIN

    for event in appointments:
        y_position = _draw_event(
            c,
            event,
            y_position,
            font_name,
            font_name_bold,
            date_color,
            background_color,
            description_color,
            alpha,
            image_stream,
        )

    c.save()
    logger.info(f"PDF successfully created: {filename} with {len(appointments)} appointments")
    return filename
