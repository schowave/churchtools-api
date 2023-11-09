import os
from datetime import datetime

from reportlab.pdfgen import canvas

from config import Config
from .utils import parse_iso_datetime
from collections import defaultdict
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.utils import ImageReader
from babel.dates import format_date


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
PAGE_WIDTH = 1152
PAGE_HEIGHT = 648
PAGE_SIZE = (PAGE_WIDTH, PAGE_HEIGHT)


def create_pdf(appointments, image_stream=None):
    current_day = datetime.now().strftime('%Y-%m-%d')
    filename = f'{current_day}_Termine.pdf'
    file_path = os.path.join(Config.FILE_DIRECTORY, filename)
    c = canvas.Canvas(file_path, pagesize=landscape(PAGE_SIZE))
    c.setTitle(filename)

    # Draw the background image first
    if image_stream:
        draw_background_image(c, image_stream, PAGE_WIDTH, PAGE_HEIGHT)

    # Organize appointments by date
    appointments_by_date = defaultdict(list)
    for a in appointments:
        start_dt = parse_iso_datetime(a['startDate'])
        date_key = start_dt.strftime('%d.%m.%Y')
        appointments_by_date[date_key].append(a)

    x_positions = [50, letter[1] / 2 + 50]
    y_position = letter[0] - 40
    column = 0
    indent = 15  # Indent for appointment entries

    for date_key in sorted(appointments_by_date.keys()):
        # Reset font and fill color at the beginning of each date block
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.black)

        # Write the date header
        start_dt = parse_iso_datetime(appointments_by_date[date_key][0]['startDate'])
        german_day_of_week = format_date(start_dt, format='EEEE', locale='de_DE')
        date_header = f"{german_day_of_week}, {date_key}"
        c.drawString(x_positions[column], y_position, date_header)
        y_position -= 20  # Space before the first appointment entry

        for a in sorted(appointments_by_date[date_key], key=lambda a: a['startDate']):
            start_dt = parse_iso_datetime(a['startDate'])
            end_dt = parse_iso_datetime(a['endDate'])
            caption = a['description']
            information = a['information']
            meeting_at = a['meetingAt']
            meeting_at_text = f", {meeting_at}" if meeting_at else ""

            # Format the time and write each appointment with indentation
            time_text = f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')} Uhr"
            c.setFont("Helvetica-Bold", 12)
            c.drawString(x_positions[column] + indent, y_position, caption)
            c.setFont("Helvetica", 10)
            c.setFillColor(colors.grey)
            c.drawString(x_positions[column] + indent, y_position - 15, f"{time_text}{meeting_at_text}")
            # Split the 'information' text by newline characters and draw each line
            info_lines = information.split('\n')
            for info_line in info_lines:
                y_position -= 15  # Adjust line spacing for each line of information
                c.drawString(x_positions[column] + indent, y_position - 15, info_line)

            c.setFillColor(colors.black)

            # Adjust y_position for the next appointment entry, with additional space
            y_position -= (15 * len(info_lines)) + 5  # Adjust spacing based on the number of lines

            # Check if we need to switch to the second column or add a new page
            if y_position < 50:
                column = 1 - column  # Toggle between 0 and 1 for columns
                y_position = letter[0] - 40  # Reset y_position for the new column

        # Add extra space after each group of appointments
        y_position -= 20

    c.save()
    return filename
