import io
from pathlib import Path

import structlog
from babel.dates import format_date
from PIL import Image, ImageColor
from reportlab.lib import colors
from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas import AgendaItem, AppointmentData, EventSummary
from app.utils import normalize_newlines, parse_iso_datetime

logger = structlog.get_logger()

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
_FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "fonts"

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
                pdfmetrics.registerFont(TTFont(font_name, str(_FONTS_DIR / f"{font_name}.ttf")))
            except Exception as e:
                logger.error(f"Error registering font {font_name}: {e}")
                font_name = FALLBACK_FONT

        bold_font_name = font_name + "-Bold"
        if bold_font_name not in pdfmetrics.getRegisteredFontNames():
            try:
                if font_name == PREFERRED_FONT:
                    # Bahnschrift uses the same file for bold
                    pdfmetrics.registerFont(TTFont(bold_font_name, str(_FONTS_DIR / f"{font_name}.ttf")))
                else:
                    pdfmetrics.registerFont(TTFont(bold_font_name, str(_FONTS_DIR / f"{font_name}-Bold.ttf")))
            except Exception as e:
                logger.error(f"Error registering bold font {bold_font_name}: {e}")
                bold_font_name = FALLBACK_FONT_BOLD
                if FALLBACK_FONT_BOLD not in pdfmetrics.getRegisteredFontNames():
                    try:
                        pdfmetrics.registerFont(TTFont(FALLBACK_FONT_BOLD, str(_FONTS_DIR / "helvetica-bold.ttf")))
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
        scale = max(width_scale, height_scale)

        scaled_width = image_width * scale
        scaled_height = image_height * scale

        x_position = (page_width - scaled_width) / 2
        y_position = (page_height - scaled_height) / 2

        canvas.drawImage(image, x_position, y_position, width=scaled_width, height=scaled_height, mask="auto")
    except Exception as e:
        logger.error(f"Error drawing background image: {e}")


def draw_logo(canvas, logo_stream, page_width, page_height):
    """Draw the logo in the bottom-right corner, right-aligned with the description boxes."""
    if logo_stream is None:
        return

    try:
        logo_stream.seek(0)
        logo = ImageReader(logo_stream)
        logo_width, logo_height = logo.getSize()

        max_logo_height = 50
        bottom_margin = 15

        scale = min(max_logo_height / logo_height, 1.0)
        scaled_width = logo_width * scale
        scaled_height = logo_height * scale

        # Align right edge with the description box right edge
        box_right_edge = LEFT_COLUMN_X + PAGE_WIDTH * SCALE_FACTOR
        x = box_right_edge - scaled_width
        y = bottom_margin

        canvas.drawImage(logo, x, y, width=scaled_width, height=scaled_height, mask="auto")
    except Exception as e:
        logger.error(f"Error drawing logo: {e}")


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


def setup_new_page(canvas_obj, image_stream, logo_stream=None):
    canvas_obj.showPage()
    canvas_obj.setPageSize(landscape(PAGE_SIZE))
    new_y_position = PAGE_HEIGHT - BOTTOM_MARGIN
    try:
        if image_stream:
            draw_background_image(canvas_obj, image_stream, *landscape(PAGE_SIZE))
        draw_logo(canvas_obj, logo_stream, *landscape(PAGE_SIZE))
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
    event: AppointmentData,
    y_position,
    font_name,
    font_name_bold,
    date_color,
    background_color,
    description_color,
    alpha,
    image_stream,
    *,
    is_first_on_page: bool = False,
    logo_stream=None,
):
    """Draw a single event on the PDF canvas. Returns (updated y_position, is_first_on_page)."""
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
        event.title, font_name_bold, font_size_large, PAGE_WIDTH - RIGHT_COLUMN_X - INDENT
    )

    # Calculate the total text block height (using actual drawing step size)
    description_step = font_size_large * LINE_SPACING_FACTOR
    total_text_height = top_padding + len(wrapped_description_lines) * description_step

    information = normalize_newlines(event.additional_info or event.information or "")
    info_max_width = LEFT_COLUMN_X + rect_width - RIGHT_COLUMN_X - INDENT
    wrapped_info_lines, _ = wrap_text(information, font_name, font_size_medium, info_max_width)

    left_col_max_width = RIGHT_COLUMN_X - LEFT_COLUMN_X - INDENT * 2
    wrapped_meeting_at_lines, _ = (
        wrap_text(event.meeting_at, font_name, font_size_medium, left_col_max_width) if event.meeting_at else ([], 0)
    )

    meeting_at_line_count = len(wrapped_meeting_at_lines) if event.meeting_at else 0
    medium_step = font_size_medium * LINE_SPACING_FACTOR
    time_and_meeting_at_height = line_height_medium + meeting_at_line_count * medium_step

    info_step = font_size_medium * LINE_SPACING_FACTOR
    actual_info_height = len(wrapped_info_lines) * info_step
    wrapped_info_height_with_padding = (actual_info_height + line_height_small) if information != "" else 0

    max_height = max(wrapped_info_height_with_padding, time_and_meeting_at_height)
    rect_height = total_text_height + max_height + line_height_medium

    # Check if we need to start a new page.
    # Skip this check for the first event on a page — it must be drawn on the
    # current page even if it's too tall, otherwise the page stays empty.
    if not is_first_on_page and y_position < (rect_height + BOTTOM_MARGIN):
        y_position = setup_new_page(c, image_stream, logo_stream)
        is_first_on_page = True

    # Limit info lines to prevent overflow into the logo area (after page break)
    info_step = font_size_medium * LINE_SPACING_FACTOR
    logo_top = 75  # keep clear of logo (15 margin + 50 height + 10 padding)
    info_start_y = y_position - top_padding - line_height_large - len(wrapped_description_lines) * description_step
    max_info_lines = max(1, int((info_start_y - logo_top) / info_step))

    if len(wrapped_info_lines) > max_info_lines:
        wrapped_info_lines = wrapped_info_lines[:max_info_lines]
        last_line = wrapped_info_lines[-1]
        while pdfmetrics.stringWidth(last_line + "...", font_name, font_size_medium) > info_max_width and last_line:
            last_line = last_line.rsplit(" ", 1)[0] if " " in last_line else last_line[:-1]
        wrapped_info_lines[-1] = last_line + "..."

        # Recalculate rect_height with truncated info
        actual_info_height = len(wrapped_info_lines) * info_step
        wrapped_info_height_with_padding = (actual_info_height + line_height_small) if information != "" else 0
        max_height = max(wrapped_info_height_with_padding, time_and_meeting_at_height)
        rect_height = total_text_height + max_height + line_height_medium

    # Ensure the background rectangle doesn't overlap the logo
    max_rect_height = y_position - 75
    if rect_height > max_rect_height:
        rect_height = max_rect_height

    draw_transparent_rectangle(
        c, LEFT_COLUMN_X, y_position - rect_height, rect_width, rect_height, background_color, alpha
    )

    text_y_position = y_position - top_padding

    # Left column: German Day and Date
    c.setFillColor(HexColor(date_color))
    c.setFont(font_name_bold, font_size_large)

    start_dt = parse_iso_datetime(event.start_date)
    end_dt = parse_iso_datetime(event.end_date)
    german_day_of_week = format_date(start_dt, format="EEEE", locale="de_DE")
    day_date_str = f"{german_day_of_week}, {start_dt.strftime('%d.%m.%Y')}"
    c.drawString(LEFT_COLUMN_X + INDENT, text_y_position - line_height_large, day_date_str)

    # Time
    c.setFillColor(HexColor(description_color))
    c.setFont(font_name, font_size_medium)
    time_str = f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')} Uhr"
    c.drawString(LEFT_COLUMN_X + INDENT, text_y_position - line_height_large - line_height_medium, time_str)

    # MeetingAt (wrapped to left column width)
    if event.meeting_at:
        meeting_at_y = text_y_position - line_height_large - line_height_medium - line_height_medium
        for ma_line in wrapped_meeting_at_lines:
            c.drawString(LEFT_COLUMN_X + INDENT, meeting_at_y, ma_line)
            meeting_at_y -= font_size_medium * LINE_SPACING_FACTOR

    # Right column: Title and Information
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

    return min(information_y_position, y_position - rect_height - line_spacing), False


def create_pdf(
    appointments, date_color, background_color, description_color, alpha, image_stream=None, logo_stream=None
) -> bytes:
    font_name, font_name_bold = _register_fonts()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(PAGE_SIZE))
    c.setTitle("appointments")

    try:
        if image_stream:
            draw_background_image(c, image_stream, *landscape(PAGE_SIZE))
        draw_logo(c, logo_stream, *landscape(PAGE_SIZE))
    except Exception as e:
        logger.error(f"Error drawing background image: {e}")

    y_position = PAGE_HEIGHT - TOP_MARGIN
    is_first_on_page = True

    for event in appointments:
        y_position, is_first_on_page = _draw_event(
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
            is_first_on_page=is_first_on_page,
            logo_stream=logo_stream,
        )

    c.save()
    logger.info(f"PDF successfully created with {len(appointments)} appointments")
    return buffer.getvalue()


def create_agenda_pdf(event_name: str, event_start: str, agenda_items: list[AgendaItem]) -> bytes:
    """Create a tabular A4 PDF for a worship service agenda."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm
    )

    font_name, font_name_bold = _register_fonts()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "AgendaTitle", parent=styles["Heading1"], fontName=font_name_bold, fontSize=16, spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        "AgendaSubtitle", parent=styles["Normal"], fontName=font_name, fontSize=10, textColor=colors.grey, spaceAfter=12
    )
    cell_style = ParagraphStyle("AgendaCell", parent=styles["Normal"], fontName=font_name, fontSize=9, leading=12)
    section_style = ParagraphStyle(
        "AgendaSection",
        parent=styles["Normal"],
        fontName=font_name_bold,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#5E8B5A"),
    )

    start_dt = parse_iso_datetime(event_start)
    date_str = start_dt.strftime("%d.%m.%Y")

    elements = []
    elements.append(Paragraph(f"Agenda — {event_name}", title_style))
    elements.append(Paragraph(date_str, subtitle_style))

    table_data = [["Zeit", "Titel", "Dauer", "Verantwortlich", "Notiz"]]
    row_styles = []

    for item in agenda_items:
        if item.type == "header":
            table_data.append([Paragraph(item.title, section_style), "", "", "", ""])
            row_idx = len(table_data) - 1
            row_styles.append(("SPAN", (0, row_idx), (4, row_idx)))
            row_styles.append(("BACKGROUND", (0, row_idx), (4, row_idx), colors.HexColor("#F0F3ED")))
            continue

        time_str = ""
        if item.start:
            dt = parse_iso_datetime(item.start)
            time_str = dt.strftime("%H:%M")

        title = item.title
        if item.type == "song" and item.song_key:
            title += f" ({item.song_key})"
            if item.song_arrangement:
                title += f"\n{item.song_arrangement}"

        table_data.append(
            [
                Paragraph(time_str, cell_style),
                Paragraph(title.replace("\n", "<br/>"), cell_style),
                Paragraph(item.duration_display, cell_style),
                Paragraph(", ".join(item.responsible_names) if item.responsible_names else "", cell_style),
                Paragraph(item.note or "", cell_style),
            ]
        )

    if len(table_data) > 1:
        col_widths = [45, 150, 40, 100, None]
        available = A4[0] - 30 * mm
        fixed = sum(w for w in col_widths if w is not None)
        col_widths[-1] = available - fixed

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        base_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5E8B5A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), font_name_bold),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8DDD0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFBF8")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        base_style.extend(row_styles)
        table.setStyle(TableStyle(base_style))
        elements.append(table)

    doc.build(elements)
    return buffer.getvalue()


def create_services_pdf(date_range: str, events: list[EventSummary]) -> bytes:
    """Create a tabular A4 PDF for service assignments across events."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm
    )

    font_name, font_name_bold = _register_fonts()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ServicesTitle", parent=styles["Heading1"], fontName=font_name_bold, fontSize=16, spaceAfter=6
    )
    cell_style = ParagraphStyle("ServicesCell", parent=styles["Normal"], fontName=font_name, fontSize=9, leading=12)
    event_header_style = ParagraphStyle(
        "ServicesEventHeader", parent=styles["Normal"], fontName=font_name_bold, fontSize=10, leading=14
    )

    elements = []
    elements.append(Paragraph(f"Dienstplan — {date_range}", title_style))
    elements.append(Spacer(1, 6))

    for event in events:
        start_dt = parse_iso_datetime(event.start_date)
        event_label = f"{start_dt.strftime('%d.%m.%Y %H:%M')} — {event.name}"
        elements.append(Paragraph(event_label, event_header_style))
        elements.append(Spacer(1, 4))

        if not event.services:
            elements.append(Paragraph("Keine Dienste eingetragen", cell_style))
            elements.append(Spacer(1, 10))
            continue

        table_data = [["Dienst", "Person", "Status"]]
        for svc in event.services:
            person = svc.person_name or "\u2014 (offen)"
            status_str = "\u2713" if svc.is_accepted else "?"
            table_data.append(
                [
                    Paragraph(svc.name, cell_style),
                    Paragraph(person, cell_style),
                    Paragraph(status_str, cell_style),
                ]
            )

        available = A4[0] - 30 * mm
        col_widths = [available * 0.35, available * 0.45, available * 0.20]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5E8B5A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), font_name_bold),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8DDD0")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFBF8")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 14))

    doc.build(elements)
    return buffer.getvalue()
