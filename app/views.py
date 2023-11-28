import os
import zipfile
from io import BytesIO
from pdf2image import convert_from_path

import requests
from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, flash, make_response, \
    session, send_file

from config import Config
from .utils import get_login_token, get_date_range_from_form, fetch_appointments, appointment_to_dict, fetch_calendars, \
    get_additional_infos, normalize_newlines, save_additional_infos
from .pdf_generator import create_pdf

main_bp = Blueprint('main_bp', __name__)


@main_bp.route('/appointments', methods=['GET', 'POST'])
def appointments():
    login_token = get_login_token()
    if not login_token:
        flash('You need to login first.', 'warning')
        return redirect(url_for('main_bp.login'))

    start_date, end_date = get_date_range_from_form()
    calendars = fetch_calendars(login_token)

    if request.method == 'POST':
        # Retrieve color values
        date_color = request.form.get('date_color')
        description_color = request.form.get('description_color')
        background_color = request.form.get('background_color')
        alpha = request.form.get('alpha')
        selected_calendar_ids = request.form.getlist('calendar_ids')
        session['selected_calendar_ids'] = selected_calendar_ids
        if 'fetch_appointments' in request.form:
            current_appointments = get_and_process_appointments(login_token, start_date, end_date)
            additional_infos = get_additional_infos(
                [appointment['id'] for appointment in session['fetched_appointments']])
            for appointment in session['fetched_appointments']:
                appointment['additional_info'] = additional_infos.get(appointment['id'], "")
            response = make_response(render_template('appointments.html', calendars=calendars,
                                                     selected_calendar_ids=selected_calendar_ids,
                                                     appointments=session['fetched_appointments'],
                                                     start_date=start_date, end_date=end_date,
                                                     base_url=Config.CHURCHTOOLS_BASE))
            response.set_cookie('fetchAppointments', 'true', max_age=1, path='/')
            return response
        elif 'generate_pdf' in request.form:
            selected_appointment_ids = request.form.getlist('appointment_id')
            save_additional_infos_from_form(selected_appointment_ids)
            pdf_filename = handle_pdf_generation(selected_appointment_ids, date_color, background_color, alpha,
                                                 description_color)
            response = make_response(redirect(url_for('main_bp.download_file', filename=pdf_filename)))
            response.set_cookie('pdfGenerated', 'true', max_age=1, path='/')
            return response
        elif 'generate_jpeg' in request.form:
            selected_appointment_ids = request.form.getlist('appointment_id')
            save_additional_infos_from_form(selected_appointment_ids)
            pdf_filename = handle_pdf_generation(selected_appointment_ids, date_color, background_color, alpha,
                                                 description_color)
            zip_buffer = handle_jpeg_generation(pdf_filename)
            response = make_response(
                send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='images.zip'))
            response.set_cookie('jpegGenerated', 'true', max_age=1, path='/')
            return response
    else:
        # On the first GET request, preselect all calendars
        # This also handles the case when the page is visited for the first time
        selected_calendar_ids = [str(calendar['id']) for calendar in calendars]

    return render_template('appointments.html', calendars=calendars, selected_calendar_ids=selected_calendar_ids,
                           start_date=start_date, end_date=end_date, base_url=Config.CHURCHTOOLS_BASE)


def save_additional_infos_from_form(selected_appointment_ids):
    # Prepare the data for bulk saving
    appointment_info_list = []
    for appointmentId in selected_appointment_ids:
        additional_info = request.form.get(f'additional_info_{appointmentId}')
        # Normalize newlines if necessary
        normalized_info = normalize_newlines(additional_info)
        appointment_info_list.append((appointmentId, normalized_info))

    # Bulk save
    save_additional_infos(appointment_info_list)


def get_and_process_appointments(login_token, start_date, end_date):
    selected_calendar_ids = request.form.getlist('calendar_ids')
    selected_calendar_ids = [int(id) for id in selected_calendar_ids if id.isdigit()]

    appointments = fetch_appointments(login_token, start_date, end_date, selected_calendar_ids)
    session['fetched_appointments'] = [appointment_to_dict(app) for app in appointments]
    return appointments


def handle_pdf_generation(appointment_ids, date_color, background_color, alpha, description_color):
    background_image_stream = get_background_image_stream()
    selected_appointments = [app for app in session.get('fetched_appointments', []) if
                             str(app['id']) in appointment_ids]
    additional_infos = get_additional_infos([appointment['id'] for appointment in selected_appointments])
    for appointment in selected_appointments:
        appointment['additional_info'] = additional_infos.get(appointment['id'], "")
    filename = create_pdf(selected_appointments, date_color, background_color, description_color, alpha,
                          background_image_stream)
    return filename


def handle_jpeg_generation(pdf_filename):
    full_pdf_path = os.path.join(Config.FILE_DIRECTORY, pdf_filename)
    images = convert_from_path(full_pdf_path)
    jpeg_files = []

    for i, image in enumerate(images):
        jpeg_stream = BytesIO()
        image.save(jpeg_stream, 'JPEG')
        jpeg_stream.seek(0)
        jpeg_files.append((f'page_{i + 1}.jpg', jpeg_stream))

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, file_bytes in jpeg_files:
            zip_file.writestr(file_name, file_bytes.read())
    zip_buffer.seek(0)
    return zip_buffer


def get_background_image_stream():
    background_image_stream = None
    if 'background_image' in request.files:
        file = request.files['background_image']
        if file and file.filename != '':
            background_image_stream = BytesIO(file.read())
    return background_image_stream


@main_bp.route('/', methods=['GET', 'POST'])
def login():
    login_token = get_login_token()
    if login_token:
        return redirect(url_for('main_bp.overview'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        data = {"password": password, "rememberMe": True, "username": username}
        response = requests.post(f'{Config.CHURCHTOOLS_BASE_URL}/api/login', json=data)

        if response.status_code == 200:
            person_id = response.json()['data']['personId']
            token_response = requests.get(f'{Config.CHURCHTOOLS_BASE_URL}/api/persons/{person_id}/logintoken',
                                          cookies=response.cookies)

            if token_response.status_code == 200:
                login_token = token_response.json()['data']
                resp = make_response(redirect(url_for('main_bp.overview')))
                resp.set_cookie('login_token', login_token)
                return resp
            else:
                flash('Failed to retrieve login token.', 'error')
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html', base_url=Config.CHURCHTOOLS_BASE)
    pass


@main_bp.route('/logout', methods=['POST'])
def logout():
    resp = make_response(redirect(url_for('main_bp.overview')))
    resp.set_cookie('login_token', '', expires=0)  # Clear the login_token cookie
    return resp
    pass


@main_bp.route('/overview')
def overview():
    login_token = get_login_token()
    if not login_token:
        return redirect(url_for('main_bp.login'))

    # Add any additional data you want to pass to your template
    return render_template('overview.html', base_url=Config.CHURCHTOOLS_BASE)
    pass


@main_bp.route('/download/<filename>')
def download_file(filename):
    # Use the safe directory when sending the file
    try:
        return send_from_directory(Config.FILE_DIRECTORY, filename, as_attachment=True)
    except FileNotFoundError:
        flash('File not found.', 'error')
        return redirect(url_for('main_bp.appointments'))  # Redirect to appointments page or a 404 page
    pass
