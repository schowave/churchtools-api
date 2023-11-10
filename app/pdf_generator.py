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
from PIL import Image
import io


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


def create_transparent_image(width, height):
    # Ensure width and height are integers
    width = int(width)
    height = int(height)
    # Create a transparent image
    transparent_img = Image.new('RGBA', (width, height), (255, 255, 255, 128))

    # Save the image to a bytes buffer
    img_buffer = io.BytesIO()
    transparent_img.save(img_buffer, format='PNG')
    img_buffer.seek(0)  # Move to the beginning of the buffer

    return img_buffer


def draw_transparent_rectangle(canvas, x, y, width, height):
    # Generate a transparent image
    transparent_image_stream = create_transparent_image(width, height)

    # Use ReportLab to draw the image
    canvas.drawImage(ImageReader(transparent_image_stream), x, y, width, height, mask='auto')


def setup_new_page(canvas_obj, image_stream):
    canvas_obj.showPage()
    canvas_obj.setPageSize(landscape(PAGE_SIZE))
    new_y_position = PAGE_HEIGHT - (PAGE_HEIGHT * 1 / 20)  # consistent with the initial y_position
    if image_stream:
        draw_background_image(canvas_obj, image_stream, *landscape(PAGE_SIZE))
    return new_y_position


def create_pdf(appointments, image_stream=None):
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

    indent = 15

    # Calculate relative positions based on page size
    left_margin_ratio = 1 / 30  # example: 1/30th of the page width
    right_column_ratio = 2 / 5  # position the right column at 2/5 of the page width

    left_column_x = PAGE_WIDTH * left_margin_ratio
    right_column_x = PAGE_WIDTH * right_column_ratio
    y_position = PAGE_HEIGHT - (PAGE_HEIGHT * 1 / 20)  # 1/10th from the top of the page

    # Calculate the height and width of the rectangle relative to page size
    rect_width = PAGE_WIDTH - (2 * left_column_x)  # width minus double the left margin

    # Define font sizes relative to page height
    base_font_size = PAGE_HEIGHT / 35  # Base font size is set relative to page height
    font_size_large = base_font_size * 1.5  # Large font for headers
    font_size_medium = base_font_size * 1.2  # Medium font for subheaders
    font_size_small = base_font_size  # Small font for details
    line_spacing = font_size_medium * 1.5  # Dynamic line spacing based on font size
    top_padding = base_font_size * 0.5  # Adjust multiplier as needed for desired padding

    for date_key, events in sorted(appointments_by_date.items()):
        for event in events:

            # Calculate the total text block height for each appointment
            total_text_height = 0
            total_text_height += top_padding  # Add top padding
            total_text_height += font_size_large + line_spacing  # For the German Day and Date
            total_text_height += font_size_medium + line_spacing  # For the Time and MeetingAt
            information = event.get('information') or ''
            details_count = len(information.split('\n'))
            total_text_height += font_size_small * details_count

            # Now set the rectangle height to match the total text height
            rect_height = total_text_height  # Add some padding

            # Check if we need to start a new page
            if y_position < (rect_height + PAGE_HEIGHT * 1 / 20):
                y_position = setup_new_page(c, image_stream)  # Reset y_position for the new page

            draw_transparent_rectangle(c, left_column_x, y_position - rect_height, rect_width, rect_height)

            # Set starting position for text, taking into account the top padding
            text_y_position = y_position - top_padding

            # Left column: German Day and Date
            c.setFillColor(HexColor(0xC1540C))
            c.setFont("Helvetica-Bold", font_size_large)
            german_day_of_week = format_date(start_dt, format='EEEE', locale='de_DE')
            day_date_str = f"{german_day_of_week}, {date_key}"
            c.drawString(left_column_x + indent, text_y_position - font_size_large, day_date_str)  # German Day and Date

            # Time
            c.setFillColor(HexColor(0x4E4E4E))
            c.setFont("Helvetica", font_size_medium)
            time_str = f"{start_dt.strftime('%H:%M')} Uhr"
            c.drawString(left_column_x + indent, y_position - (2 * line_spacing), time_str)  # Time

            # MeetingAt - draw this below the Time, on the third row
            if event['meetingAt']:
                meeting_at_str = f"{event['meetingAt']}"  # Add prefix for clarity
                # Move this to the third row by subtracting an additional line_spacing
                c.drawString(left_column_x + indent, y_position - (3 * line_spacing), meeting_at_str)

            # Right column: Caption and Information
            c.setFillColor(black)
            c.setFont("Helvetica-Bold", font_size_large)
            c.drawString(right_column_x, text_y_position - font_size_large, event['description'])  # Caption

            c.setFillColor(HexColor(0x4E4E4E))
            c.setFont("Helvetica", font_size_small)

            # Draw the information text, checking if it is not None
            if information:
                details_y_position = y_position - (2 * line_spacing)
                for detail in information.split('\n'):
                    c.drawString(right_column_x, details_y_position, detail)
                    details_y_position -= font_size_small * 1.5

            # Update y_position for next event
            y_position -= (rect_height + line_spacing)  # space between rectangles

    c.save()
    return filename
