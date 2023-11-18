import os
from config import Config
from .utils import parse_iso_datetime
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, HexColor
from datetime import datetime
from collections import defaultdict
from babel.dates import format_date
from PIL import Image, ImageColor
import io
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def draw_background_image(canvas, image_stream, page_width, page_height):
    # Load the image
    image = ImageReader(image_stream)
    image_width, image_height = image.getSize()

    # Calculate scale factors
    width_scale = page_width / image_width
    height_scale = page_height / image_height

    # Choose the smaller of the two scale factors to maintain aspect ratio
    scale = min(width_scale, height_scale)

    # Calculate the new dimensions of the image
    scaled_width = image_width * scale
    scaled_height = image_height * scale

    # Calculate position to center the image on the canvas
    x_position = (page_width - scaled_width) / 2
    y_position = (page_height - scaled_height) / 2

    # Draw the image on the canvas with the new dimensions
    canvas.drawImage(image, x_position, y_position, width=scaled_width, height=scaled_height, mask='auto')


# Define the 16:9 page size in points
PAGE_WIDTH = 1200
PAGE_HEIGHT = 675
PAGE_SIZE = (PAGE_WIDTH, PAGE_HEIGHT)


def create_transparent_image(width, height, background_color, alpha):
    # Ensure width and height are integers
    width = int(width)
    height = int(height)

    # Convert the color string to an RGBA tuple
    rgba_color = ImageColor.getcolor(background_color, "RGBA")

    # Replace the alpha component with the specified alpha value
    rgba_color = rgba_color[:-1] + (int(alpha),)

    # Create and return the transparent image
    return Image.new('RGBA', (width, height), rgba_color)

    # Save the image to a bytes buffer
    img_buffer = io.BytesIO()
    transparent_img.save(img_buffer, format='PNG')
    img_buffer.seek(0)  # Move to the beginning of the buffer

    return img_buffer


def draw_transparent_rectangle(canvas, x, y, width, height, background_color, alpha):
    # Generate a transparent image
    transparent_image_stream = create_transparent_image(width, height, background_color, alpha)

    # Use ReportLab to draw the image
    canvas.drawImage(ImageReader(transparent_image_stream), x, y, width, height, mask='auto')


def setup_new_page(canvas_obj, image_stream):
    canvas_obj.showPage()
    canvas_obj.setPageSize(landscape(PAGE_SIZE))
    new_y_position = PAGE_HEIGHT - (PAGE_HEIGHT * 1 / 20)  # consistent with the initial y_position
    if image_stream:
        draw_background_image(canvas_obj, image_stream, *landscape(PAGE_SIZE))
    return new_y_position


def wrap_text(text, font_name, line_height, max_width):
    """
    Wrap text to fit within a given width when rendered in a given font and size.
    Returns a list of lines and the total height the text block will require.
    Preserves original line breaks and wraps text that exceeds max_width.
    """
    # Register the font if it hasn't been registered yet
    if not pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, f'{font_name}.ttf'))

    wrapped_lines = []
    text_height = 0

    # Split the text by original line breaks first
    original_lines = text.split('\n')

    for line in original_lines:
        # If the line fits within the maximum width, add it directly
        if pdfmetrics.stringWidth(line, font_name, line_height) <= max_width:
            wrapped_lines.append(line)
            text_height += line_height
        else:
            # If the line is too wide, split it further
            words = line.split()
            wrapped_line = []
            while words:
                # Keep adding words until the line is too wide
                wrapped_line.append(words.pop(0))
                test_line = ' '.join(wrapped_line + words[:1])
                if pdfmetrics.stringWidth(test_line, font_name, line_height) > max_width:
                    # When the next word would make it too wide,
                    # the line is done and should be appended
                    wrapped_lines.append(' '.join(wrapped_line))
                    text_height += line_height
                    wrapped_line = []
            # Add any remaining words as a new line
            if wrapped_line:
                wrapped_lines.append(' '.join(wrapped_line))
                text_height += line_height

    return wrapped_lines, text_height


def create_pdf(appointments, date_color, background_color, description_color, alpha, image_stream=None):
    font_name = 'Bahnschrift'
    font_name_bold = font_name+'-Bold'
    current_day = datetime.now().strftime('%Y-%m-%d')
    filename = f'{current_day}_Termine.pdf'
    file_path = os.path.join(Config.FILE_DIRECTORY, filename)
    c = canvas.Canvas(file_path, pagesize=landscape(PAGE_SIZE))
    c.setTitle(filename)

    # Draw the background image first
    if image_stream:
        draw_background_image(c, image_stream, *landscape(PAGE_SIZE))

    # Organize appointments by date
    appointments_by_date = defaultdict(list)
    for a in appointments:
        start_dt = parse_iso_datetime(a['startDate'])
        date_key = start_dt.strftime('%d.%m.%Y')
        appointments_by_date[date_key].append(a)

    indent = PAGE_WIDTH * 1 / 40

    # Calculate relative positions based on page size
    left_margin_ratio = 1 / 20  # example: 1/30th of the page width
    right_column_ratio = 2 / 5  # position the right column at 2/5 of the page width

    left_column_x = PAGE_WIDTH * left_margin_ratio
    right_column_x = PAGE_WIDTH * right_column_ratio
    y_position = PAGE_HEIGHT - (PAGE_HEIGHT * 1 / 20)  # 1/10th from the top of the page

    # Calculate the height and width of the rectangle relative to page size
    rect_width = PAGE_WIDTH - (2 * left_column_x)  # width minus double the left margin

    # Define font sizes relative to page height
    base_font_size = PAGE_HEIGHT / 35  # Base font size is set relative to page height
    line_height_factor = 1.4
    font_size_large = base_font_size * 1.5  # Large font for headers
    line_height_large = font_size_large * line_height_factor
    font_size_medium = base_font_size * 1.2  # Medium font for subheaders
    line_height_medium = font_size_medium * line_height_factor
    font_size_small = base_font_size  # Small font for details
    line_height_small = font_size_small * line_height_factor
    line_spacing = base_font_size * 1.5  # Dynamic line spacing based on font size
    top_padding = base_font_size * 0.8  # Adjust multiplier as needed for desired padding

    for date_key, events in sorted(appointments_by_date.items()):
        for event in events:

            # Calculate the total text block height for each appointment
            total_text_height = 0
            total_text_height += top_padding  # Add top padding
            total_text_height += line_height_large  # For the German Day and Date and Caption

            information = event.get('additional_info') or event.get('information') or ''
            details_count = len(information.split('\n'))

            # Wrap the information text if it exceeds the width of the rectangle
            wrapped_info_lines, wrapped_info_height = wrap_text(
                information, font_name, line_height_medium, rect_width - right_column_x * 0.5
            )

            time_and_meeting_at_height = line_height_medium + (line_height_medium if event['meetingAt'] != '' else 0)
            wrapped_info_height_with_padding = (wrapped_info_height + line_height_small) if information != '' else 0

            # Get the maximum of the Time and MeetingAt and the WrappedInfoHeight
            max_height = max(wrapped_info_height_with_padding, time_and_meeting_at_height)

            # Now set the rectangle height to match the total text height
            rect_height = total_text_height + max_height + line_height_medium  # Add some padding

            information_font_size = font_size_medium

            # Check if we need to start a new page
            if y_position < (rect_height + PAGE_HEIGHT * 1 / 20):
                y_position = setup_new_page(c, image_stream)  # Reset y_position for the new page

            draw_transparent_rectangle(c, left_column_x, y_position - rect_height, rect_width, rect_height,
                                       background_color, alpha)

            # Set starting position for text, taking into account the top padding
            text_y_position = y_position - top_padding

            # Left column: German Day and Date
            c.setFillColor(HexColor(date_color))
            c.setFont(font_name_bold, font_size_large)

            start_dt = parse_iso_datetime(event['startDate'])
            end_dt = parse_iso_datetime(event['endDate'])
            german_day_of_week = format_date(start_dt, format='EEEE', locale='de_DE')
            day_date_str = f"{german_day_of_week}, {date_key}"
            c.drawString(left_column_x + indent, text_y_position - line_height_large,
                         day_date_str)  # German Day and Date

            # Time
            c.setFillColor(HexColor(description_color))
            c.setFont(font_name, font_size_medium)
            time_str = f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')} Uhr"
            c.drawString(left_column_x + indent, text_y_position - line_height_large - line_height_medium,
                         time_str)  # Time

            # MeetingAt - draw this below the Time, on the third row
            if event['meetingAt']:
                meeting_at_str = f"{event['meetingAt']}"  # Add prefix for clarity
                # Move this to the third row by subtracting an additional line_spacing
                c.drawString(left_column_x + indent,
                             text_y_position - line_height_large - line_height_medium - line_height_medium,
                             meeting_at_str)

            # Right column: Caption and Information
            c.setFillColor(black)
            c.setFont(font_name_bold, font_size_large)
            c.drawString(right_column_x, text_y_position - line_height_large, event['description'])  # Caption

            c.setFillColor(HexColor(description_color))
            c.setFont(font_name, information_font_size)

            # Draw the information text, checking if it is not None
            if information:
                details_y_position = text_y_position - line_height_large - line_height_medium
                for detail in wrapped_info_lines:
                    c.drawString(right_column_x, details_y_position, detail)
                    details_y_position -= information_font_size * 1.5

            # Update y_position for next event
            y_position -= (rect_height + line_spacing)  # space between rectangles

    c.save()
    return filename
