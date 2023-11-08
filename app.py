import os
import requests
import pytz
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, make_response, send_from_directory
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from collections import defaultdict
from babel.dates import format_date
from io import BytesIO

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
churchtools_base_url = os.environ.get('CHURCHTOOLS_BASE_URL', 'https://evkila.church.tools')
FILE_DIRECTORY = os.path.join(app.root_path, 'saved_files')
os.makedirs(FILE_DIRECTORY, exist_ok=True)


def get_login_token():
    return request.cookies.get('login_token')


def parse_iso_datetime(dt_str):
    # Create a timezone-aware datetime object in UTC if the string ends with 'Z'
    if dt_str.endswith('Z'):
        dt = datetime.fromisoformat(dt_str.rstrip('Z'))
        utc_dt = dt.replace(tzinfo=pytz.utc)
    else:
        # If the string does not end with 'Z', parse it as is
        utc_dt = datetime.fromisoformat(dt_str)

    # Convert the timezone from UTC to Europe/Berlin
    berlin_tz = pytz.timezone('Europe/Berlin')
    berlin_dt = utc_dt.astimezone(berlin_tz)
    return berlin_dt


def make_login_request(username, password):
    data = {"password": password, "rememberMe": True, "username": username}
    return requests.post(f'{churchtools_base_url}/api/login', json=data)


def fetch_appointments(login_token, start_date, end_date):
    berlin_tz = pytz.timezone('Europe/Berlin')
    start_date_datetime = berlin_tz.localize(datetime.strptime(start_date, '%Y-%m-%d'))
    end_date_datetime = berlin_tz.localize(datetime.strptime(end_date, '%Y-%m-%d'))
    end_date_replace = end_date_datetime.replace(hour=23, minute=59, second=59)

    headers = {'Authorization': f'Login {login_token}'}
    appointments = []
    seen_ids = set()  # Set to track seen appointment IDs

    for calendar_id in [47, 1, 2]:
        url = f'{churchtools_base_url}/api/calendars/{calendar_id}/appointments'
        response = requests.get(url, headers=headers)
        if response.ok:
            for appointment in response.json()['data']:
                appointment_id = appointment['base']['id']
                appointment_start_date = appointment['base']['startDate']
                # Combine the checks for seen ID and date range into a single condition
                if appointment_id not in seen_ids and start_date_datetime <= parse_iso_datetime(
                        appointment_start_date) <= end_date_replace:
                    seen_ids.add(appointment_id)
                    appointments.append(appointment)

    return appointments


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
    file_path = os.path.join(FILE_DIRECTORY, filename)
    c = canvas.Canvas(file_path, pagesize=landscape(PAGE_SIZE))
    c.setTitle(filename)

    # Draw the background image first
    if image_stream:
        draw_background_image(c, image_stream, PAGE_WIDTH, PAGE_HEIGHT)

    # Organize appointments by date
    appointments_by_date = defaultdict(list)
    for a in appointments:
        start_dt = parse_iso_datetime(a['base']['startDate'])
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
        start_dt = parse_iso_datetime(appointments_by_date[date_key][0]['base']['startDate'])
        german_day_of_week = format_date(start_dt, format='EEEE', locale='de_DE')
        date_header = f"{german_day_of_week}, {date_key}"
        c.drawString(x_positions[column], y_position, date_header)
        y_position -= 20  # Space before the first appointment entry

        for a in sorted(appointments_by_date[date_key], key=lambda a: a['base']['startDate']):
            base = a['base']
            start_dt = parse_iso_datetime(base['startDate'])
            end_dt = parse_iso_datetime(base['endDate'])
            caption = base.get('caption', 'No Caption')
            address = base.get('address') or {}
            meeting_at = address.get('meetingAt', '')
            # Construct the meeting_at text with conditional comma
            meeting_at_text = f", {meeting_at}" if meeting_at else ""

            # Format the time and write each appointment with indentation
            time_text = f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')} Uhr"
            c.setFont("Helvetica-Bold", 12)
            c.drawString(x_positions[column] + indent, y_position, caption)
            c.setFont("Helvetica", 10)
            c.setFillColor(colors.grey)
            c.drawString(x_positions[column] + indent, y_position - 15, f"{time_text}{meeting_at_text}")
            c.setFillColor(colors.black)

            # Adjust y_position for the next appointment entry, with additional space
            y_position -= 35

            # Check if we need to switch to the second column or add a new page
            if y_position < 50:
                column = 1 - column  # Toggle between 0 and 1 for columns
                y_position = letter[0] - 40  # Reset y_position for the new column

        # Add extra space after each group of appointments
        y_position -= 20

    c.save()
    return filename


@app.route('/appointments', methods=['GET', 'POST'])
def appointments():
    login_token = get_login_token()
    if not login_token:
        flash('You need to login first.', 'warning')
        return redirect(url_for('login'))
    start_date, end_date = get_date_range_from_form()
    if request.method == 'POST':
        appointments = fetch_appointments(login_token, start_date, end_date)
        background_image_stream = None
        # Check if the post request has the file part
        if 'background_image' in request.files:
            file = request.files['background_image']
            if file and file.filename != '':
                # Read the image file into a BytesIO stream
                background_image_stream = BytesIO(file.read())
        filename = create_pdf(appointments, background_image_stream)
        return redirect(url_for('download_file', filename=filename))
    return render_template('appointments.html', start_date=start_date, end_date=end_date)


def get_date_range_from_form():
    today = datetime.today()
    next_sunday = today + timedelta(days=(6 - today.weekday()) % 7)
    sunday_after_next = next_sunday + timedelta(weeks=1)
    start_date = request.form.get('start_date', next_sunday.strftime('%Y-%m-%d'))
    end_date = request.form.get('end_date', sunday_after_next.strftime('%Y-%m-%d'))
    return start_date, end_date


@app.route('/', methods=['GET', 'POST'])
def login():
    login_token = get_login_token()
    if login_token:
        return redirect(url_for('overview'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        data = {"password": password, "rememberMe": True, "username": username}
        response = requests.post(f'{churchtools_base_url}/api/login', json=data)

        if response.status_code == 200:
            person_id = response.json()['data']['personId']
            token_response = requests.get(f'{churchtools_base_url}/api/persons/{person_id}/logintoken',
                                          cookies=response.cookies)

            if token_response.status_code == 200:
                login_token = token_response.json()['data']
                resp = make_response(redirect(url_for('overview')))
                resp.set_cookie('login_token', login_token)
                return resp
            else:
                flash('Failed to retrieve login token.', 'error')
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout', methods=['POST'])
def logout():
    resp = make_response(redirect(url_for('overview')))
    resp.set_cookie('login_token', '', expires=0)  # Clear the login_token cookie
    return resp


@app.route('/overview')
def overview():
    login_token = get_login_token()
    if not login_token:
        return redirect(url_for('login'))

    # Add any additional data you want to pass to your template
    return render_template('overview.html')


@app.route('/download/<filename>')
def download_file(filename):
    # Use the safe directory when sending the file
    try:
        return send_from_directory(FILE_DIRECTORY, filename, as_attachment=True)
    except FileNotFoundError:
        flash('File not found.', 'error')
        return redirect(url_for('appointments'))  # Redirect to appointments page or a 404 page


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
