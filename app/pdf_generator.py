import os
from config import Config
from .utils import parse_iso_datetime
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, white
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
PAGE_WIDTH = 800
PAGE_HEIGHT = 450
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

    left_column_x = 100
    right_column_x = 400
    y_position = landscape(PAGE_SIZE)[1] - 100
    indent = 15
    bottom_margin = 50  # Bottom margin before adding a new page

    for date_key, events in sorted(appointments_by_date.items()):
        for event in events:
            rect_height = 100
            rect_width = landscape(PAGE_SIZE)[0] - 200

            # Check if we need to start a new page
            if y_position < (rect_height + bottom_margin):
                c.showPage()
                c.setPageSize(landscape(PAGE_SIZE))
                y_position = landscape(PAGE_SIZE)[1] - 100
                if image_stream:
                    draw_background_image(c, image_stream, *landscape(PAGE_SIZE))

            draw_transparent_rectangle(c, left_column_x, y_position - rect_height, rect_width, rect_height)

            # Left column: German Day and Date
            c.setFillColor(black)
            c.setFont("Helvetica-Bold", 14)
            german_day_of_week = format_date(start_dt, format='EEEE', locale='de_DE')
            day_date_str = f"{german_day_of_week}, {date_key}"
            c.drawString(left_column_x + indent, y_position - 25, day_date_str)  # German Day and Date

            # Time and MeetingAt
            c.setFont("Helvetica", 12)
            time_str = f"{start_dt.strftime('%H:%M')} Uhr"
            time_width = c.stringWidth(time_str, "Helvetica", 12)
            c.drawString(left_column_x + indent, y_position - 45, time_str)  # Time

            if event['meetingAt']:
                meeting_at_str = f"{event['meetingAt']}"
                c.drawString(left_column_x + indent + time_width + 10, y_position - 45,
                             meeting_at_str)  # MeetingAt, adjust spacing as needed

            # Right column: Caption and Information
            c.setFont("Helvetica-Bold", 12)
            c.drawString(right_column_x, y_position - 25, event['description'])  # Caption

            c.setFont("Helvetica", 10)
            details_y_position = y_position - 45
            for detail in event['information'].split('\n'):
                c.drawString(right_column_x, details_y_position, detail)
                details_y_position -= 15  # Adjust line spacing

            # Update y_position for next event
            y_position -= (rect_height + 20)

    c.save()
    return filename
